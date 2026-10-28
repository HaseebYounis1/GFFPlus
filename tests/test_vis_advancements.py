#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sourcecode" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vx.gff.Settings import Settings
from vx.gff.MakeProjection import MakeProjection
from vx.gff.XAI import ContrastiveSubspaceExplainer
from vx.gff.graphtree.graphtree_pure import Metrics, NeighborJoining, DistanceMatrix
from vx.com.py.projection.MDSP import MDSP


def _naive_silhouette(X, y, z):
    """Original O(n^2) Python loop implementation for exact parity verification."""
    n = len(X)
    c = len(z)
    dat = [0.0 for _ in range(n * 2)]
    for i in range(n):
        dat[i * 2] = float(X[i][0])
        dat[i * 2 + 1] = float(X[i][1])

    silhouette = 0.0
    for i in range(n):
        xi = dat[i * 2]
        yi = dat[i * 2 + 1]
        ci = z[y[i]]
        a = [0.0 for _ in range(c)]
        ac = [0.0 for _ in range(c)]
        for j in range(n):
            if i != j:
                xj = dat[j * 2]
                yj = dat[j * 2 + 1]
                cj = z[y[j]]
                d = ((xi - xj) ** 2 + (yi - yj) ** 2) ** 0.5
                a[cj] += d
                ac[cj] += 1.0
        if ac[ci] > 0:
            a_i = a[ci] / ac[ci]
        else:
            a_i = 0.0
        b_i = float("inf")
        for j in range(c):
            if j != ci and ac[j] > 0.0:
                b_i = min(b_i, a[j] / ac[j])
        if not np.isfinite(b_i):
            b_i = 0.0
        denom = max(a_i, b_i)
        s_i = (b_i - a_i) / denom if denom > 0 else 0.0
        silhouette += s_i
    return round(silhouette / n, 4)


class TestVisAdvancements(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.orig_data_path = Settings.DATA_PATH
        Settings.DATA_PATH = os.path.join(self.tmpdir.name, "")
        self.dataset_id = "vis_bench_ds"
        self.ds_dir = Path(Settings.DATA_PATH) / self.dataset_id
        self.ds_dir.mkdir(parents=True, exist_ok=True)

        rng = np.random.default_rng(42)
        n = 120
        # Construct 3 well-separated clusters across features
        # Cluster 0 (rows 0..39): high f0, low f1, low f_hidden
        # Cluster 1 (rows 40..79): low f0, high f1, low f_hidden
        # Cluster 2 (rows 80..119): low f0, high f1, HIGH f_hidden (mixed with Cluster 1 if only f0,f1 are selected!)
        f0 = np.concatenate([rng.normal(4.0, 0.4, 40), rng.normal(-2.0, 0.4, 40), rng.normal(-2.0, 0.4, 40)])
        f1 = np.concatenate([rng.normal(-2.0, 0.4, 40), rng.normal(3.5, 0.4, 40), rng.normal(3.5, 0.4, 40)])
        f_redundant = f0 * 0.98 + rng.normal(0.0, 0.05, n)
        f_counterfactual = np.concatenate([rng.normal(0.0, 0.3, 40), rng.normal(-3.5, 0.3, 40), rng.normal(4.5, 0.3, 40)])
        f_noise = rng.normal(0.0, 1.0, n)
        target = np.array([0] * 40 + [1] * 40 + [2] * 40, dtype=int)

        df = pd.DataFrame({
            "f0_primary": f0,
            "f1_secondary": f1,
            "f2_redundant": f_redundant,
            "f3_counterfactual": f_counterfactual,
            "f4_noise": f_noise,
            "class_target": target,
        })
        for fname in ("original.csv", "working.csv", "transform.csv"):
            df.to_csv(self.ds_dir / fname, index=False)

    def tearDown(self):
        Settings.DATA_PATH = self.orig_data_path
        self.tmpdir.cleanup()

    def test_vectorized_silhouette_exact_parity(self):
        rng = np.random.default_rng(19)
        X = rng.normal(size=(90, 2)).tolist()
        y = [int(i % 3) for i in range(90)]
        z = {0: 0, 1: 1, 2: 2}

        expected = _naive_silhouette(X, y, z)
        actual = Metrics.compute_silhoute(X, y, z)
        self.assertAlmostEqual(expected, actual, places=4)

        pointwise = Metrics.compute_pointwise_silhouette(X, y, z)
        self.assertEqual(len(pointwise), 90)
        self.assertAlmostEqual(round(float(np.mean(pointwise)), 4), actual, places=4)

    def test_vectorized_neighbor_joining_tree_topology(self):
        # Classic 4-taxon additive distance matrix where (0,1) and (2,3) form cherries
        D = np.array([
            [0.0, 0.2, 0.7, 0.8],
            [0.2, 0.0, 0.6, 0.7],
            [0.7, 0.6, 0.0, 0.3],
            [0.8, 0.7, 0.3, 0.0],
        ])
        dm = DistanceMatrix(4)
        for i in range(4):
            for j in range(i + 1, 4):
                dm.setValue(i, j, float(D[i, j]))
        res = NeighborJoining(dm).execute()
        self.assertEqual(len(res["nodes"]), 4 + 2)  # 4 leaves + 2 internal nodes
        self.assertEqual(len(res["edges"]), 5)
        for edge in res["edges"]:
            self.assertGreaterEqual(edge["weight"], 0.0)

    def test_mdsp_executes_without_future_warning(self):
        rng = np.random.default_rng(7)
        X = rng.normal(size=(25, 4))
        import warnings
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", FutureWarning)
            coords = MDSP(X).execute()
            future_warns = [w for w in caught if issubclass(w.category, FutureWarning)]
            self.assertEqual(len(future_warns), 0)
        self.assertEqual(len(coords), 25)
        self.assertEqual(len(coords[0]), 2)

    def test_projection_quality_and_pointwise_fidelity(self):
        mp = MakeProjection()
        mp.execute({
            "file": self.dataset_id,
            "projection": "pca",
            "instanceproximity": "Euclidean",
            "target": 5,
            "featureselected": [0, 1, 3],
        })
        self.assertIn("quality", mp.data)
        q = mp.data["quality"]
        for key in ("trustworthiness", "continuity", "shepard_corr", "mean_fidelity", "silhouette"):
            self.assertIn(key, q)
        self.assertGreater(q["trustworthiness"], 0.8)
        self.assertGreater(q["continuity"], 0.8)
        self.assertGreater(q["mean_fidelity"], 0.4)
        self.assertIsNotNone(q["silhouette"])
        self.assertEqual(len(mp.data["points"]), 120)
        for pt in mp.data["points"]:
            self.assertIn("fidelity", pt)
            self.assertGreaterEqual(pt["fidelity"], 0.0)
            self.assertLessEqual(pt["fidelity"], 1.0)

    def test_contrastive_and_counterfactual_subspace_explainer(self):
        # Suppose the user only selected f0_primary (0) and f1_secondary (1).
        # In this 2D subspace, Cluster 1 (rows 40..79, class 1) and Cluster 2 (rows 80..119, class 2)
        # overlap! When the user brushes rows 40..119 as Group A, the explainer should:
        # 1. Identify f1_secondary and f0_primary as the primary contrastive drivers vs. Rest (rows 0..39).
        # 2. Identify f3_counterfactual (index 3, unselected) as the #1 counterfactual feature to add
        #    because it resolves the target-class impurity inside Group A and has low redundancy!
        explainer = ContrastiveSubspaceExplainer()
        res = explainer.execute(Settings.DATA_PATH, {
            "file": self.dataset_id,
            "target": 5,
            "featureselected": [0, 1],
            "group_a_ids": list(range(40, 120)),
        })
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["comparison_mode"], "a_vs_rest")
        self.assertEqual(res["group_a_count"], 80)
        self.assertEqual(res["group_b_count"], 40)
        self.assertAlmostEqual(res["group_a_purity"], 0.5, places=2)

        # Statistical rigour fields check
        self.assertIn("contrastive_features", res)
        self.assertIn("counterfactual_candidates", res)
        f1_info = res["by_feature_id"]["1"]
        self.assertIn("t_statistic", f1_info)
        self.assertIn("p_value", f1_info)
        self.assertIn("fdr_q_value", f1_info)
        self.assertIn("is_significant", f1_info)
        self.assertLess(f1_info["p_value"], 0.001)
        self.assertTrue(f1_info["is_significant"])

        # Top counterfactual unselected feature must be f3_counterfactual (id=3)
        self.assertTrue(len(res["top_counterfactual"]) > 0)
        best_cf = res["top_counterfactual"][0]
        self.assertEqual(best_cf["id"], 3)
        self.assertEqual(best_cf["name"], "f3_counterfactual")
        # Redundant feature f2_redundant (id=2) must have high redundancy (> 0.9)
        f2_info = res["by_feature_id"]["2"]
        self.assertGreater(f2_info["redundancy"], 0.9)

        # Also test two-group mode (Group A = rows 40..79 vs Group B = rows 80..119)
        res_ab = explainer.execute(Settings.DATA_PATH, {
            "file": self.dataset_id,
            "target": 5,
            "featureselected": [0, 1],
            "group_a_ids": list(range(40, 80)),
            "group_b_ids": list(range(80, 120)),
        })
        self.assertEqual(res_ab["status"], "ok")
        self.assertEqual(res_ab["comparison_mode"], "a_vs_b")
        self.assertEqual(res_ab["top_counterfactual"][0]["id"], 3)

    def test_subspace_perturbation_preview_ghost_trails(self):
        # Preview adding f3_counterfactual (3) to [0, 1]: Silhouette and separability should improve!
        preview = MakeProjection.preview_perturbation({
            "file": self.dataset_id,
            "target": 5,
            "instanceproximity": "Euclidean",
            "featureselected": [0, 1],
            "candidate_feature": 3,
            "action": "add",
        })
        self.assertEqual(preview["status"], "ok")
        self.assertEqual(preview["action"], "add")
        self.assertEqual(preview["base_feature_count"], 2)
        self.assertEqual(preview["perturbed_feature_count"], 3)
        self.assertEqual(len(preview["trails"]), 120)
        self.assertGreater(preview["mean_displacement"], 0.01)
        # Adding f3_counterfactual separates class 1 and class 2, so 2D Silhouette increases
        self.assertGreater(preview["quality_delta"]["silhouette"], 0.05)


if __name__ == "__main__":
    unittest.main()
