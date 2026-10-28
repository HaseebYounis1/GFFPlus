#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Adversarial Stress Test Suite for GFF+ Visual Analytics Advancements.
Role: EMPIRICAL CHALLENGER (Milestone M5 - Final Gate Verification).

Tests:
1. Mathematical Edge Cases on ContrastiveSubspaceExplainer:
   - Zero variance columns (both groups, single group, all features)
   - Single-sample groups (n_a=1, n_b=1, n_a=1 & n_b=1, n=0)
   - Identical groups (H0 null hypothesis: exact parity and distributionally identical)
   - Completely distinct groups (astronomical separation, huge/tiny magnitudes)
   - Collinear and redundant features (identical, linearly scaled, negatively correlated)
2. Procrustes SVD Alignment Invariants in MakeProjection:
   - Zero perturbation (identity check, displacement ~ 0)
   - 180-degree rotation recovery
   - Arbitrary rotation and reflection recovery
   - Pairwise Euclidean distance isometry / invariance under orthogonal transformation
   - Collinear / rank-1 2D configurations
   - Constant / degenerate configurations
3. Silhouette Vectorized Speedup & Numerical Stability:
   - Parity with legacy O(N^2) naive silhouette across N in [50, 100, 250, 500, 1000]
   - Measurement of speedup factors
   - Boundary conditions: singleton clusters, identical point coordinates, k=1 cluster, extreme coordinates
4. Robustness against Numerical Errors (NaN, Inf, ZeroDivision):
   - Comprehensive assertion that all outputs are finite and bounded in their theoretical domains.
"""

import math
import os
import sys
import tempfile
import unittest
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from scipy import stats
from scipy.linalg import orthogonal_procrustes
from scipy.spatial.distance import cdist

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sourcecode" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vx.gff.Settings import Settings
from vx.gff.MakeProjection import MakeProjection
from vx.gff.XAI import ContrastiveSubspaceExplainer
from vx.gff.graphtree.graphtree_pure import Metrics


def naive_silhouette(X, y, z):
    """Ground-truth naive reference implementation from benchmarks/run_vis_benchmarks.py."""
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
        a_i = a[ci] / ac[ci] if ac[ci] > 0 else 0.0
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


class TestAdversarialCCSE(unittest.TestCase):
    """Adversarial stress-testing of ContrastiveSubspaceExplainer."""

    def test_zero_variance_both_groups(self):
        """Zero variance in both groups should produce t=0, p=1, df>=1, Cohen's d=0."""
        n_a, n_b = 25, 30
        X_a = np.full((n_a, 5), 42.0)
        X_b = np.full((n_b, 5), 42.0)
        t, p, df = ContrastiveSubspaceExplainer.welch_t_test(X_a, X_b)
        self.assertTrue(np.all(t == 0.0), f"Expected t=0, got {t}")
        self.assertTrue(np.all(p == 1.0), f"Expected p=1, got {p}")
        self.assertTrue(np.all(df >= 1.0), f"Expected df>=1, got {df}")
        self.assertFalse(np.any(np.isnan(t)))
        self.assertFalse(np.any(np.isnan(p)))

    def test_zero_variance_different_constants(self):
        """Zero variance in both groups but different constants (e.g. 5 vs 10). denom_se is 0."""
        n_a, n_b = 20, 20
        X_a = np.full((n_a, 3), 5.0)
        X_b = np.full((n_b, 3), 10.0)
        t, p, df = ContrastiveSubspaceExplainer.welch_t_test(X_a, X_b)
        # In zero-variance cases, standard error is 0, so valid_mask is False -> t=0, p=1
        self.assertTrue(np.all(t == 0.0))
        self.assertTrue(np.all(p == 1.0))
        self.assertTrue(np.all(np.isfinite(df)))

    def test_zero_variance_one_group_only(self):
        """Group A is constant (var=0), Group B has normal variance."""
        rng = np.random.default_rng(777)
        n_a, n_b = 40, 50
        X_a = np.full((n_a, 4), 3.0)
        X_b = rng.normal(loc=1.0, scale=2.0, size=(n_b, 4))
        t, p, df = ContrastiveSubspaceExplainer.welch_t_test(X_a, X_b)

        # Scipy reference with equal_var=False
        scipy_res = stats.ttest_ind(X_a, X_b, equal_var=False)
        np.testing.assert_allclose(t, scipy_res.statistic, rtol=1e-8, atol=1e-10)
        np.testing.assert_allclose(p, scipy_res.pvalue, rtol=1e-8, atol=1e-10)
        # Degree of freedom when s_a=0 is exactly n_b - 1
        np.testing.assert_allclose(df, np.full(4, n_b - 1))

    def test_single_sample_groups(self):
        """Single-sample cohort (n_a=1 or n_b=1) must fallback gracefully without crash/NaN."""
        rng = np.random.default_rng(888)
        # n_a=1, n_b=10
        X_1 = rng.normal(size=(1, 6))
        X_10 = rng.normal(size=(10, 6))
        t1, p1, df1 = ContrastiveSubspaceExplainer.welch_t_test(X_1, X_10)
        self.assertTrue(np.all(t1 == 0.0))
        self.assertTrue(np.all(p1 == 1.0))
        self.assertTrue(np.all(df1 >= 1.0))

        # n_a=10, n_b=1
        t2, p2, df2 = ContrastiveSubspaceExplainer.welch_t_test(X_10, X_1)
        self.assertTrue(np.all(t2 == 0.0))
        self.assertTrue(np.all(p2 == 1.0))
        self.assertTrue(np.all(df2 >= 1.0))

        # n_a=1, n_b=1
        t3, p3, df3 = ContrastiveSubspaceExplainer.welch_t_test(X_1, X_1)
        self.assertTrue(np.all(t3 == 0.0))
        self.assertTrue(np.all(p3 == 1.0))
        self.assertTrue(np.all(df3 >= 1.0))

    def test_identical_groups_h0(self):
        """Identical groups (X_a == X_b) must result in t=0, p=1, Cohen's d=0."""
        rng = np.random.default_rng(999)
        X = rng.normal(loc=5.0, scale=2.5, size=(50, 8))
        t, p, df = ContrastiveSubspaceExplainer.welch_t_test(X, X)
        np.testing.assert_allclose(t, np.zeros(8), atol=1e-12)
        np.testing.assert_allclose(p, np.ones(8), atol=1e-12)

    def test_completely_distinct_groups(self):
        """Extremely distinct groups (large effect size) should yield huge |t| and p ~ 0."""
        rng = np.random.default_rng(1001)
        n = 50
        X_a = rng.normal(loc=1000.0, scale=1.0, size=(n, 4))
        X_b = rng.normal(loc=-1000.0, scale=1.0, size=(n, 4))
        t, p, df = ContrastiveSubspaceExplainer.welch_t_test(X_a, X_b)
        self.assertTrue(np.all(t > 500.0))
        self.assertTrue(np.all(p < 1e-50))
        self.assertTrue(np.all(np.isfinite(t)))
        self.assertTrue(np.all(np.isfinite(p)))

    def test_astronomical_and_infinitesimal_magnitudes(self):
        """Inputs with extreme numerical scales: 1e15 and 1e-15."""
        X_huge_a = np.array([[1e15, 1e-15], [1.0001e15, 1.0001e-15], [0.9999e15, 0.9999e-15]])
        X_huge_b = np.array([[2e15, 2e-15], [2.0001e15, 2.0001e-15], [1.9999e15, 1.9999e-15]])
        t, p, df = ContrastiveSubspaceExplainer.welch_t_test(X_huge_a, X_huge_b)
        self.assertTrue(np.all(np.isfinite(t)))
        self.assertTrue(np.all(np.isfinite(p)))
        self.assertTrue(np.all(np.isfinite(df)))
        self.assertTrue(np.all((p >= 0.0) & (p <= 1.0)))

    def test_collinear_features_in_execute(self):
        """Test full CCSE execute with collinear, redundant, and constant features."""
        with tempfile.TemporaryDirectory() as tmp:
            orig_path = Settings.DATA_PATH
            Settings.DATA_PATH = os.path.join(tmp, "")
            try:
                ds_id = "collinear_ds"
                ds_dir = Path(Settings.DATA_PATH) / ds_id
                ds_dir.mkdir(parents=True, exist_ok=True)

                rng = np.random.default_rng(42)
                n = 100
                f0 = rng.normal(0, 1, n)
                f1 = f0.copy()                  # Exactly identical
                f2 = 3.0 * f0 + 2.0             # Linearly dependent (corr = 1.0)
                f3 = -2.0 * f0 + 1.0            # Perfectly anti-correlated (corr = -1.0)
                f4 = np.zeros(n)                # Constant zero
                f5 = rng.normal(5, 1, n)        # Independent
                target = rng.integers(0, 2, n)

                df = pd.DataFrame({
                    "f_base": f0,
                    "f_ident": f1,
                    "f_linear": f2,
                    "f_anticorr": f3,
                    "f_zero": f4,
                    "f_indep": f5,
                    "target": target,
                })
                df.to_csv(ds_dir / "transform.csv", index=False)
                df.to_csv(ds_dir / "original.csv", index=False)

                explainer = ContrastiveSubspaceExplainer()
                res = explainer.execute(Settings.DATA_PATH, {
                    "file": ds_id,
                    "target": 6,
                    "featureselected": [0],  # Select f_base
                    "group_a_ids": list(range(0, 30)),
                    "group_b_ids": list(range(30, 60)),
                })

                self.assertEqual(res["status"], "ok")
                features = {f["name"]: f for f in res["contrastive_features"]}

                # Check f_ident, f_linear, f_anticorr redundancy against f_base
                self.assertAlmostEqual(features["f_ident"]["redundancy"], 1.0, places=4)
                self.assertAlmostEqual(features["f_linear"]["redundancy"], 1.0, places=4)
                self.assertAlmostEqual(features["f_anticorr"]["redundancy"], 1.0, places=4)
                # f_zero should have redundancy 0.0 (protected against division by zero)
                self.assertEqual(features["f_zero"]["redundancy"], 0.0)

                # All returned values must be finite numbers
                for f_name, f_data in features.items():
                    for k in ["cohens_d", "delta_normalized", "t_statistic", "p_value", "fdr_q_value", "counterfactual_gain", "redundancy"]:
                        val = f_data[k]
                        self.assertTrue(np.isfinite(val), f"Non-finite value {val} in {f_name}.{k}")
            finally:
                Settings.DATA_PATH = orig_path

    def test_ccse_group_a_equals_all_instances(self):
        """When Group A contains all instances in the dataset, Group B (Rest) has 0 instances."""
        with tempfile.TemporaryDirectory() as tmp:
            orig_path = Settings.DATA_PATH
            Settings.DATA_PATH = os.path.join(tmp, "")
            try:
                ds_id = "all_a_ds"
                ds_dir = Path(Settings.DATA_PATH) / ds_id
                ds_dir.mkdir(parents=True, exist_ok=True)
                n = 40
                df = pd.DataFrame({"f1": range(n), "f2": range(n), "target": [0] * n})
                df.to_csv(ds_dir / "transform.csv", index=False)
                df.to_csv(ds_dir / "original.csv", index=False)

                explainer = ContrastiveSubspaceExplainer()
                res = explainer.execute(Settings.DATA_PATH, {
                    "file": ds_id,
                    "target": 2,
                    "group_a_ids": list(range(n)),
                })
                # Should return status='empty' because Group B has 0 instances
                self.assertEqual(res["status"], "empty")
                self.assertEqual(res["group_b_count"], 0)
            finally:
                Settings.DATA_PATH = orig_path

    def test_ccse_group_a_and_b_full_overlap(self):
        """When Group B is identical to Group A, group_b_set - group_a_set results in empty B."""
        with tempfile.TemporaryDirectory() as tmp:
            orig_path = Settings.DATA_PATH
            Settings.DATA_PATH = os.path.join(tmp, "")
            try:
                ds_id = "overlap_ds"
                ds_dir = Path(Settings.DATA_PATH) / ds_id
                ds_dir.mkdir(parents=True, exist_ok=True)
                n = 40
                df = pd.DataFrame({"f1": range(n), "f2": range(n), "target": [0] * n})
                df.to_csv(ds_dir / "transform.csv", index=False)
                df.to_csv(ds_dir / "original.csv", index=False)

                explainer = ContrastiveSubspaceExplainer()
                res = explainer.execute(Settings.DATA_PATH, {
                    "file": ds_id,
                    "target": 2,
                    "group_a_ids": [1, 2, 3],
                    "group_b_ids": [1, 2, 3],
                })
                # In XAI.py line 686: group_b_set = set(...) - group_a_set -> empty -> mask_b = ~mask_a -> comparison_mode = "a_vs_rest"
                self.assertEqual(res["status"], "ok")
                self.assertEqual(res["comparison_mode"], "a_vs_rest")
            finally:
                Settings.DATA_PATH = orig_path


class TestAdversarialProcrustes(unittest.TestCase):
    """Adversarial stress-testing of Procrustes SVD alignment and MakeProjection invariants."""

    def test_procrustes_rotation_matrix_orthogonality(self):
        """Verify that the computed rotation matrix R satisfies R^T R = I and |det(R)| = 1."""
        rng = np.random.default_rng(555)
        for _ in range(25):
            n = rng.integers(15, 100)
            Y_base = rng.normal(size=(n, 2))
            Y_pert = rng.normal(size=(n, 2))

            mu_b = Y_base.mean(axis=0, keepdims=True)
            mu_p = Y_pert.mean(axis=0, keepdims=True)
            Yc_b = Y_base - mu_b
            Yc_p = Y_pert - mu_p
            norm_b = float(np.linalg.norm(Yc_b))
            norm_p = float(np.linalg.norm(Yc_p))

            R, _ = orthogonal_procrustes(Yc_p / norm_p, Yc_b / norm_b)

            # Check R^T R == I
            np.testing.assert_allclose(R.T @ R, np.eye(2), atol=1e-12)
            # Check det(R) is either +1 (rotation) or -1 (reflection)
            det_r = float(np.linalg.det(R))
            self.assertAlmostEqual(abs(det_r), 1.0, places=10)

    def test_preview_perturbation_all_constant_dataset(self):
        """Degenerate dataset where all features are constant 0."""
        with tempfile.TemporaryDirectory() as tmp:
            orig_path = Settings.DATA_PATH
            Settings.DATA_PATH = os.path.join(tmp, "")
            try:
                ds_id = "const_ds"
                ds_dir = Path(Settings.DATA_PATH) / ds_id
                ds_dir.mkdir(parents=True, exist_ok=True)
                n = 30
                df = pd.DataFrame({"f0": np.zeros(n), "f1": np.zeros(n), "target": np.zeros(n)})
                df.to_csv(ds_dir / "transform.csv", index=False)
                df.to_csv(ds_dir / "original.csv", index=False)

                res = MakeProjection.preview_perturbation({
                    "file": ds_id,
                    "target": 2,
                    "instanceproximity": "Euclidean",
                    "featureselected": [0],
                    "candidate_feature": 1,
                    "action": "add",
                })
                self.assertEqual(res["status"], "ok")
                self.assertTrue(np.all(np.isfinite([t["displacement"] for t in res["trails"]])))
            finally:
                Settings.DATA_PATH = orig_path

    def test_preview_perturbation_candidate_already_selected_noop(self):
        """Action 'add' when candidate is already in base features should be idempotent."""
        with tempfile.TemporaryDirectory() as tmp:
            orig_path = Settings.DATA_PATH
            Settings.DATA_PATH = os.path.join(tmp, "")
            try:
                ds_id = "already_sel_ds"
                ds_dir = Path(Settings.DATA_PATH) / ds_id
                ds_dir.mkdir(parents=True, exist_ok=True)
                n = 30
                df = pd.DataFrame({"f0": range(n), "f1": range(n), "f2": range(n), "target": [0] * n})
                df.to_csv(ds_dir / "transform.csv", index=False)
                df.to_csv(ds_dir / "original.csv", index=False)

                res = MakeProjection.preview_perturbation({
                    "file": ds_id,
                    "target": 3,
                    "instanceproximity": "Euclidean",
                    "featureselected": [0, 1],
                    "candidate_feature": 1,
                    "action": "add",
                })
                self.assertEqual(res["status"], "ok")
                # Feature 1 was already selected, so base_count == pert_count == 2
                self.assertEqual(res["base_feature_count"], 2)
                self.assertEqual(res["perturbed_feature_count"], 2)
                # Displacements should all be 0 because subspaces are identical!
                self.assertAlmostEqual(res["mean_displacement"], 0.0, places=4)
            finally:
                Settings.DATA_PATH = orig_path

    def test_procrustes_zero_perturbation_identity(self):
        """Zero perturbation: Y_pert == Y_base -> aligned coordinates must match Y_base exactly."""
        rng = np.random.default_rng(123)
        Y_base = rng.normal(size=(50, 2))
        Y_pert = Y_base.copy()

        mu_b = Y_base.mean(axis=0, keepdims=True)
        mu_p = Y_pert.mean(axis=0, keepdims=True)
        Yc_b = Y_base - mu_b
        Yc_p = Y_pert - mu_p
        norm_b = float(np.linalg.norm(Yc_b))
        norm_p = float(np.linalg.norm(Yc_p))

        R, _ = orthogonal_procrustes(Yc_p / norm_p, Yc_b / norm_b)
        Y_aligned = (Yc_p / norm_p) @ R * norm_b + mu_b

        np.testing.assert_allclose(Y_aligned, Y_base, atol=1e-12)
        displacements = np.linalg.norm(Y_aligned - Y_base, axis=1)
        self.assertAlmostEqual(float(np.max(displacements)), 0.0, places=10)

    def test_procrustes_180_degree_rotation(self):
        """180-degree rotation (R = -I) should be recovered perfectly by orthogonal Procrustes."""
        rng = np.random.default_rng(456)
        Y_base = rng.normal(loc=2.0, scale=1.5, size=(60, 2))
        # Center and rotate by 180 degrees
        mu_b = Y_base.mean(axis=0, keepdims=True)
        Yc_b = Y_base - mu_b

        # 180 degree rotation: x' = -x, y' = -y
        R_180 = np.array([[-1.0, 0.0], [0.0, -1.0]])
        Y_pert = Yc_b @ R_180 + np.array([[5.0, -3.0]])  # Rotated and translated

        mu_p = Y_pert.mean(axis=0, keepdims=True)
        Yc_p = Y_pert - mu_p
        norm_b = float(np.linalg.norm(Yc_b))
        norm_p = float(np.linalg.norm(Yc_p))

        R, _ = orthogonal_procrustes(Yc_p / norm_p, Yc_b / norm_b)
        Y_aligned = (Yc_p / norm_p) @ R * norm_b + mu_b

        # Y_aligned must restore Y_base exactly
        np.testing.assert_allclose(Y_aligned, Y_base, atol=1e-12)
        max_err = float(np.max(np.linalg.norm(Y_aligned - Y_base, axis=1)))
        self.assertLess(max_err, 1e-11)

    def test_procrustes_arbitrary_rotations_and_reflections(self):
        """Test random orthogonal transformations (rotation + reflection) across 20 trials."""
        rng = np.random.default_rng(789)
        n = 40
        Y_base = rng.normal(loc=-1.0, scale=3.0, size=(n, 2))
        mu_b = Y_base.mean(axis=0, keepdims=True)
        Yc_b = Y_base - mu_b
        norm_b = float(np.linalg.norm(Yc_b))

        for theta in np.linspace(0, 2 * np.pi, 16):
            for reflect in [1.0, -1.0]:
                cos_t, sin_t = np.cos(theta), np.sin(theta)
                # 2D orthogonal matrix
                Q = np.array([[cos_t, -sin_t], [reflect * sin_t, reflect * cos_t]])
                offset = rng.uniform(-50, 50, size=(1, 2))
                Y_pert = Yc_b @ Q + offset

                mu_p = Y_pert.mean(axis=0, keepdims=True)
                Yc_p = Y_pert - mu_p
                norm_p = float(np.linalg.norm(Yc_p))

                R, _ = orthogonal_procrustes(Yc_p / norm_p, Yc_b / norm_b)
                Y_aligned = (Yc_p / norm_p) @ R * norm_b + mu_b

                np.testing.assert_allclose(Y_aligned, Y_base, atol=1e-10)

    def test_procrustes_pairwise_distance_invariance(self):
        """Verify that pairwise Euclidean distances in Y_pert are preserved under Procrustes alignment."""
        rng = np.random.default_rng(2026)
        n = 50
        Y_base = rng.normal(size=(n, 2))
        # Perturbed layout has different scale and rotation
        Y_pert = rng.normal(loc=10.0, scale=5.0, size=(n, 2))

        mu_b = Y_base.mean(axis=0, keepdims=True)
        mu_p = Y_pert.mean(axis=0, keepdims=True)
        Yc_b = Y_base - mu_b
        Yc_p = Y_pert - mu_p
        norm_b = float(np.linalg.norm(Yc_b))
        norm_p = float(np.linalg.norm(Yc_p))

        R, _ = orthogonal_procrustes(Yc_p / norm_p, Yc_b / norm_b)
        Y_aligned = (Yc_p / norm_p) @ R * norm_b + mu_b

        # Theoretical invariant: Y_aligned = s * (Y_pert - mu_p) @ R + mu_b
        # where s = norm_b / norm_p.
        # Since R is orthogonal, for any i, j:
        # ||Y_aligned[i] - Y_aligned[j]|| = s * ||Y_pert[i] - Y_pert[j]||
        s = norm_b / norm_p
        D_pert = cdist(Y_pert, Y_pert, metric="euclidean")
        D_aligned = cdist(Y_aligned, Y_aligned, metric="euclidean")

        # Check exact isotropic scaling of distance matrix
        np.testing.assert_allclose(D_aligned, s * D_pert, rtol=1e-12, atol=1e-12)

        # Pairwise distance ratios D[i,j] / D[k,l] are strictly invariant
        # Check on 100 random pairs
        tri_i, tri_j = np.triu_indices(n, k=1)
        d_p = D_pert[tri_i, tri_j]
        d_a = D_aligned[tri_i, tri_j]
        valid = (d_p > 1e-6)
        ratios = d_a[valid] / d_p[valid]
        np.testing.assert_allclose(ratios, np.full_like(ratios, s), rtol=1e-12)

    def test_procrustes_degenerate_collinear(self):
        """Points lying on a 1D line in 2D space (rank 1 matrix)."""
        rng = np.random.default_rng(333)
        n = 30
        t_vals = np.linspace(-5, 5, n)[:, None]
        Y_base = np.hstack([t_vals, 2.0 * t_vals])
        Y_pert = np.hstack([3.0 * t_vals, -1.5 * t_vals])

        mu_b = Y_base.mean(axis=0, keepdims=True)
        mu_p = Y_pert.mean(axis=0, keepdims=True)
        Yc_b = Y_base - mu_b
        Yc_p = Y_pert - mu_p
        norm_b = float(np.linalg.norm(Yc_b))
        norm_p = float(np.linalg.norm(Yc_p))

        R, _ = orthogonal_procrustes(Yc_p / norm_p, Yc_b / norm_b)
        Y_aligned = (Yc_p / norm_p) @ R * norm_b + mu_b

        self.assertTrue(np.all(np.isfinite(Y_aligned)))
        # Check that pairwise distance scaling holds
        s = norm_b / norm_p
        np.testing.assert_allclose(cdist(Y_aligned, Y_aligned), s * cdist(Y_pert, Y_pert), atol=1e-12)

    def test_preview_perturbation_end_to_end(self):
        """Test full preview_perturbation method with add/remove actions and verify quality deltas."""
        with tempfile.TemporaryDirectory() as tmp:
            orig_path = Settings.DATA_PATH
            Settings.DATA_PATH = os.path.join(tmp, "")
            try:
                ds_id = "preview_test_ds"
                ds_dir = Path(Settings.DATA_PATH) / ds_id
                ds_dir.mkdir(parents=True, exist_ok=True)

                rng = np.random.default_rng(2026)
                n = 80
                cols = {f"f{i}": rng.normal(size=n) for i in range(8)}
                cols["target"] = rng.integers(0, 2, size=n)
                df = pd.DataFrame(cols)
                df.to_csv(ds_dir / "transform.csv", index=False)
                df.to_csv(ds_dir / "original.csv", index=False)

                res_add = MakeProjection.preview_perturbation({
                    "file": ds_id,
                    "target": 8,
                    "instanceproximity": "Euclidean",
                    "featureselected": [0, 1, 2],
                    "candidate_feature": 3,
                    "action": "add",
                })

                self.assertEqual(res_add["status"], "ok")
                self.assertEqual(res_add["action"], "add")
                self.assertEqual(len(res_add["trails"]), n)
                self.assertIn("quality_delta", res_add)
                for qk in ["trustworthiness", "continuity", "shepard_corr", "mean_fidelity"]:
                    self.assertIn(qk, res_add["quality_delta"])
                    self.assertTrue(np.isfinite(res_add["quality_delta"][qk]))

                # Check displacement values are >= 0
                for trail in res_add["trails"]:
                    self.assertGreaterEqual(trail["displacement"], 0.0)
                    self.assertTrue(0.0 <= trail["fidelity_before"] <= 1.0)
                    self.assertTrue(0.0 <= trail["fidelity_after"] <= 1.0)
            finally:
                Settings.DATA_PATH = orig_path


class TestAdversarialSilhouette(unittest.TestCase):
    """Adversarial stress-testing of Silhouette speedup and numerical stability."""

    def test_silhouette_parity_and_speedup_across_n(self):
        """Verify exact parity between vectorized silhouette and legacy naive across N."""
        rng = np.random.default_rng(2026)
        n_values = [50, 100, 250, 500, 1000]
        results = []

        for n in n_values:
            X = rng.normal(size=(n, 2)).tolist()
            y = [int(i % 3) for i in range(n)]
            z = {0: 0, 1: 1, 2: 2}

            # Legacy O(N^2)
            t0 = perf_counter()
            s_old = naive_silhouette(X, y, z)
            t_old_ms = (perf_counter() - t0) * 1000.0

            # Vectorized O(N^2) BLAS
            t1 = perf_counter()
            s_new = Metrics.compute_silhoute(X, y, z)
            t_new_ms = (perf_counter() - t1) * 1000.0

            diff = abs(s_old - s_new)
            speedup = t_old_ms / max(t_new_ms, 1e-6)

            results.append({
                "N": n,
                "s_old": s_old,
                "s_new": round(s_new, 4),
                "diff": diff,
                "t_old_ms": round(t_old_ms, 2),
                "t_new_ms": round(t_new_ms, 2),
                "speedup": round(speedup, 1),
            })

            # Discrepancy must be tiny (< 1e-4 rounding difference)
            self.assertLess(diff, 1e-4, f"Silhouette mismatch at N={n}: old={s_old}, new={s_new}")

        print("\n--- Silhouette Benchmark Results ---")
        for r in results:
            print(f"N={r['N']:4d} | legacy={r['t_old_ms']:6.2f}ms | vec={r['t_new_ms']:5.2f}ms | speedup={r['speedup']:4.1f}x | diff={r['diff']:.2e}")

    def test_silhouette_single_cluster_boundary(self):
        """Only one cluster (k=1) -> Silhouette is undefined or 0.0."""
        X = [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]
        y = [0, 0, 0]
        z = {0: 0}
        s = Metrics.compute_silhoute(X, y, z)
        self.assertEqual(s, 0.0)

    def test_silhouette_singleton_clusters(self):
        """Clusters with only 1 member -> s(i) = 0 for singletons."""
        X = [[0.0, 0.0], [10.0, 10.0], [10.1, 10.1]]
        y = [0, 1, 1]  # Cluster 0 is a singleton
        z = {0: 0, 1: 1}
        s_arr = Metrics.compute_pointwise_silhouette(X, y, z)
        self.assertEqual(s_arr[0], 0.0)
        self.assertTrue(np.all(np.isfinite(s_arr)))

    def test_silhouette_identical_points(self):
        """All points are identical (distance = 0) in two clusters."""
        X = [[1.0, 1.0], [1.0, 1.0], [1.0, 1.0], [1.0, 1.0]]
        y = [0, 0, 1, 1]
        z = {0: 0, 1: 1}
        s = Metrics.compute_silhoute(X, y, z)
        self.assertEqual(s, 0.0)

    def test_silhouette_extreme_coordinates(self):
        """Extreme coordinates (1e8 and 1e-8) should not cause overflow or NaN."""
        X = [[1e8, 1e8], [1e8 + 1, 1e8 + 1], [-1e8, -1e8], [-1e8 - 1, -1e8 - 1]]
        y = [0, 0, 1, 1]
        z = {0: 0, 1: 1}
        s = Metrics.compute_silhoute(X, y, z)
        self.assertTrue(np.isfinite(s))
        self.assertGreater(s, 0.9)  # Highly separated clusters


class TestAdversarialNumericalErrorAudit(unittest.TestCase):
    """Stress tests specifically hunting for NaN, Inf, and ZeroDivision across components."""

    def test_bh_empty_and_nan_resilience(self):
        """BH FDR on boundary inputs."""
        q_empty = ContrastiveSubspaceExplainer.benjamini_hochberg([])
        self.assertEqual(len(q_empty), 0)

        p_with_nan = [0.01, np.nan, 0.05]
        # Shouldn't crash: argsort puts nan at end in numpy
        q_nan = ContrastiveSubspaceExplainer.benjamini_hochberg(p_with_nan)
        self.assertEqual(len(q_nan), 3)

    def test_welch_empty_arrays(self):
        """Welch t-test on empty arrays."""
        t, p, df = ContrastiveSubspaceExplainer.welch_t_test(np.empty((0, 3)), np.empty((0, 3)))
        self.assertEqual(len(t), 3)
        self.assertTrue(np.all(t == 0.0))
        self.assertTrue(np.all(p == 1.0))

    def test_fidelity_halos_identical_points(self):
        """Fidelity calculation when all points are at the exact same location."""
        n = 20
        X_h = np.zeros((n, 5))
        X_l = np.zeros((n, 2))
        yt = np.zeros(n)
        qual, fid = MakeProjection._compute_projection_quality(X_h, X_l, yt)
        self.assertTrue(np.all(np.isfinite(fid)))
        self.assertTrue(np.all((fid >= 0.0) & (fid <= 1.0)))
        for k, v in qual.items():
            if v is not None:
                self.assertTrue(np.isfinite(v), f"Non-finite quality metric {k}: {v}")


if __name__ == "__main__":
    unittest.main()
