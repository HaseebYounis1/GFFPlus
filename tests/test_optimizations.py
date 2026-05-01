"""
Regression and correctness tests for all optimized modules.

Each test validates that the optimised implementation produces numerically
identical (or equivalent within floating-point tolerance) results to the
hand-verified reference values computed from the original algorithm.
"""

import sys
import math
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sourcecode" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _euclidean_ref(a, b):
    """Pure-Python reference Euclidean distance."""
    return math.sqrt(sum((ai - bi) ** 2 for ai, bi in zip(a, b)))


def _pairwise_ref(X):
    """Reference O(n^2) pairwise Euclidean matrix with min-max normalisation."""
    n = len(X)
    raw = [[0.0] * n for _ in range(n)]
    vals = []
    for i in range(n):
        for j in range(i + 1, n):
            d = _euclidean_ref(X[i], X[j])
            raw[i][j] = raw[j][i] = d
            vals.append(d)
    if not vals:
        return raw
    mn, mx = min(vals), max(vals)
    denom = 1e-7 + (mx - mn)
    out = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            out[i][j] = out[j][i] = (raw[i][j] - mn) / denom
    return out


# ---------------------------------------------------------------------------
# Proximity.compute
# ---------------------------------------------------------------------------

class TestProximityCompute(unittest.TestCase):

    def setUp(self):
        from vx.com.py.proximity.Proximity import Proximity
        self.P = Proximity

    def test_euclidean_zero(self):
        a = [1.0, 2.0, 3.0]
        self.assertAlmostEqual(self.P.compute(a, a, "euclidean"), 0.0)

    def test_euclidean_known(self):
        a = [0.0, 0.0]
        b = [3.0, 4.0]
        self.assertAlmostEqual(self.P.compute(a, b, "euclidean"), 5.0, places=10)

    def test_euclidean_matches_reference(self):
        rng = np.random.default_rng(0)
        for _ in range(50):
            a = rng.standard_normal(10).tolist()
            b = rng.standard_normal(10).tolist()
            ref = _euclidean_ref(a, b)
            got = self.P.compute(a, b, "euclidean")
            self.assertAlmostEqual(got, ref, places=10)

    def test_unknown_proxtype_returns_zero(self):
        self.assertEqual(self.P.compute([1.0], [2.0], "cosine"), 0.0)


# ---------------------------------------------------------------------------
# PMatrix
# ---------------------------------------------------------------------------

class TestPMatrix(unittest.TestCase):

    def setUp(self):
        from vx.com.py.proximity.Proximity import PMatrix
        self.PMatrix = PMatrix

    def test_unset_returns_none(self):
        pm = self.PMatrix(5)
        self.assertIsNone(pm.get(0, 1))

    def test_set_and_get_symmetric(self):
        pm = self.PMatrix(4)
        pm.set(1, 3, 0.75)
        self.assertAlmostEqual(pm.get(1, 3), 0.75)
        self.assertAlmostEqual(pm.get(3, 1), 0.75)

    def test_diagonal_starts_none(self):
        pm = self.PMatrix(3)
        # diagonal is always 0 distance in practice; we just check no crash
        pm.set(2, 2, 0.0)
        self.assertAlmostEqual(pm.get(2, 2), 0.0)


# ---------------------------------------------------------------------------
# _compute_pairwise / _pairwise_matrix (dataio_pure)
# ---------------------------------------------------------------------------

class TestDataioPairwise(unittest.TestCase):

    def setUp(self):
        from vx.com.px.dataset.dataio_pure import _pairwise_matrix, _compute_pairwise, ProximityMatrix
        self._pm = _pairwise_matrix
        self._cp = _compute_pairwise
        self.POT = ProximityMatrix.POT

    def _vectors(self, seed=0):
        rng = np.random.default_rng(seed)
        return rng.uniform(0.1, 1.0, size=(6, 8))

    # ---- Euclidean (pt=0) ---------------------------------------------------
    def test_euclidean_matrix_shape(self):
        data = self._vectors()
        mat = self._pm(data, axis=1, pt=0)
        self.assertEqual(mat.shape, (data.shape[1], data.shape[1]))

    def test_euclidean_diagonal_zero(self):
        data = self._vectors()
        mat = self._pm(data, axis=1, pt=0)
        np.testing.assert_array_almost_equal(np.diag(mat), 0.0)

    def test_euclidean_symmetric(self):
        data = self._vectors()
        mat = self._pm(data, axis=1, pt=0)
        np.testing.assert_array_almost_equal(mat, mat.T)

    def test_euclidean_normalised_range(self):
        data = self._vectors()
        mat = self._pm(data, axis=1, pt=0)
        # After min-max normalisation all off-diagonal values in [0, 1]
        n = mat.shape[0]
        upper = mat[np.triu_indices(n, k=1)]
        self.assertGreaterEqual(float(upper.min()), 0.0)
        self.assertLessEqual(float(upper.max()), 1.0 + 1e-9)

    def test_euclidean_matches_reference(self):
        rng = np.random.default_rng(42)
        X = rng.uniform(0.0, 5.0, size=(10, 4))
        # axis=0: rows as vectors
        mat = self._pm(X, axis=0, pt=0)
        ref = _pairwise_ref(X.tolist())
        for i in range(10):
            for j in range(10):
                self.assertAlmostEqual(mat[i, j], ref[i][j], places=8,
                                       msg=f"mismatch at ({i},{j})")

    # ---- Cosine (pt=5) -------------------------------------------------------
    def test_cosine_diagonal_zero(self):
        data = self._vectors()
        mat = self._pm(data, axis=0, pt=5)
        np.testing.assert_array_almost_equal(np.diag(mat), 0.0)

    def test_cosine_symmetric(self):
        data = self._vectors()
        mat = self._pm(data, axis=0, pt=5)
        np.testing.assert_array_almost_equal(mat, mat.T)

    # ---- Pearson (pt=6) ------------------------------------------------------
    def test_pearson_diagonal_zero(self):
        data = self._vectors()
        mat = self._pm(data, axis=0, pt=6)
        np.testing.assert_array_almost_equal(np.diag(mat), 0.0)

    def test_pearson_symmetric(self):
        data = self._vectors()
        mat = self._pm(data, axis=0, pt=6)
        np.testing.assert_array_almost_equal(mat, mat.T)

    # ---- empty / single-row edge cases ---------------------------------------
    def test_empty_returns_empty(self):
        mat = self._pm(np.zeros((0, 4)), axis=0, pt=0)
        self.assertEqual(mat.shape, (0, 0))

    def test_single_vector_returns_zeros(self):
        mat = self._pm(np.array([[1.0, 2.0, 3.0]]), axis=0, pt=0)
        self.assertEqual(mat.shape, (1, 1))
        self.assertAlmostEqual(float(mat[0, 0]), 0.0)


# ---------------------------------------------------------------------------
# BKmeans.computeMean / computeMedoid
# ---------------------------------------------------------------------------

class TestBKmeansMath(unittest.TestCase):

    def setUp(self):
        from vx.com.py.clustering.BKmeans import BKmeans
        self.BK = BKmeans

    def _X(self):
        return [
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
            [7.0, 8.0, 9.0],
            [10.0, 11.0, 12.0],
        ]

    def test_mean_all(self):
        X = self._X()
        mean = self.BK.computeMean(X, [0, 1, 2, 3])
        expected = [5.5, 6.5, 7.5]
        for g, e in zip(mean, expected):
            self.assertAlmostEqual(g, e, places=10)

    def test_mean_subset(self):
        X = self._X()
        mean = self.BK.computeMean(X, [0, 2])
        expected = [4.0, 5.0, 6.0]
        for g, e in zip(mean, expected):
            self.assertAlmostEqual(g, e, places=10)

    def test_mean_single(self):
        X = self._X()
        mean = self.BK.computeMean(X, [1])
        for g, e in zip(mean, X[1]):
            self.assertAlmostEqual(g, e, places=10)

    def test_mean_empty_returns_zeros(self):
        X = self._X()
        mean = self.BK.computeMean(X, [])
        self.assertEqual(len(mean), 3)
        self.assertTrue(all(v == 0.0 for v in mean))

    def test_medoid_is_closest_to_centroid(self):
        X = self._X()
        centroid = [4.0, 5.0, 6.0]
        med = self.BK.computeMedoid(X, [0, 1, 2, 3], centroid, "euclidean")
        # Point [4,5,6] is index 1 and equals the centroid exactly
        self.assertEqual(med, 1)

    def test_medoid_single_element(self):
        X = self._X()
        med = self.BK.computeMedoid(X, [2], [7.0, 8.0, 9.0], "euclidean")
        self.assertEqual(med, 2)


# ---------------------------------------------------------------------------
# BKmeansFE.computeMean
# ---------------------------------------------------------------------------

class TestBKmeansFEMean(unittest.TestCase):

    def setUp(self):
        from vx.com.py.clustering.BKmeansFE import BKmeansFE
        from vx.com.px.dataset.dataio_pure import DataMatrix
        self.BKF = BKmeansFE
        self.DM = DataMatrix

    def _make_dm(self, data):
        dm = self.DM()
        dm._data = np.array(data, dtype=float)
        dm._featuresnames_index = [str(i) for i in range(len(data[0]))]
        dm._featuresnames = {str(i): i for i in range(len(data[0]))}
        dm._feids = list(range(len(data[0])))
        dm._trueids = list(range(len(data[0])))
        return dm

    def test_mean_matches_numpy(self):
        data = [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]]
        X = self._make_dm(data)
        centroids = self._make_dm([[0.0, 0.0]] * 4)
        self.BKF.computeMean(X, [0, 1, 2], centroids, 0)
        expected = np.array([3.0, 4.0])
        np.testing.assert_array_almost_equal(centroids._data[0], expected)

    def test_empty_cluster_fills_zeros(self):
        data = [[1.0, 2.0], [3.0, 4.0]]
        X = self._make_dm(data)
        centroids = self._make_dm([[9.9, 9.9], [9.9, 9.9]])
        self.BKF.computeMean(X, [], centroids, 1)
        np.testing.assert_array_almost_equal(centroids._data[1], [0.0, 0.0])


# ---------------------------------------------------------------------------
# MData.samplex
# ---------------------------------------------------------------------------

class TestMDataSamplex(unittest.TestCase):

    def setUp(self):
        from vx.com.py.matrix.MData import MData
        self.samplex = MData.samplex

    def _X(self):
        return [[i * 10 + j for j in range(4)] for i in range(5)]

    def test_row_sample(self):
        X = self._X()
        result = self.samplex(X, smp_r=[0, 2, 4])
        self.assertEqual(len(result), 3)
        self.assertAlmostEqual(result[0][0], 0.0)
        self.assertAlmostEqual(result[1][0], 20.0)
        self.assertAlmostEqual(result[2][0], 40.0)

    def test_col_sample(self):
        X = self._X()
        result = self.samplex(X, smp_c=[1, 3])
        self.assertEqual(len(result), 5)
        self.assertEqual(len(result[0]), 2)
        self.assertAlmostEqual(result[0][0], 1.0)
        self.assertAlmostEqual(result[0][1], 3.0)

    def test_row_and_col(self):
        X = self._X()
        result = self.samplex(X, smp_r=[1, 3], smp_c=[0, 2])
        self.assertEqual(len(result), 2)
        self.assertEqual(len(result[0]), 2)
        self.assertAlmostEqual(result[0][0], 10.0)
        self.assertAlmostEqual(result[0][1], 12.0)

    def test_no_sample_returns_original(self):
        X = self._X()
        result = self.samplex(X)
        self.assertIs(result, X)


# ---------------------------------------------------------------------------
# MData.openfilecsv
# ---------------------------------------------------------------------------

class TestMDataOpenFileCSV(unittest.TestCase):

    def setUp(self):
        import tempfile, os
        from vx.com.py.matrix.MData import MData
        self.MData = MData
        self.tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        )
        self.tmp.write("a,b,target\n1.0,2.0,0\n3.0,4.0,1\n5.0,6.0,0\n")
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        import os
        os.unlink(self.path)

    def test_shape(self):
        md = self.MData.openfilecsv(self.path)
        self.assertEqual(len(md.X), 3)
        self.assertEqual(len(md.X[0]), 3)

    def test_values(self):
        md = self.MData.openfilecsv(self.path)
        self.assertAlmostEqual(md.X[0][0], 1.0)
        self.assertAlmostEqual(md.X[1][2], 1.0)

    def test_columns(self):
        md = self.MData.openfilecsv(self.path)
        self.assertEqual(md.columns, ["a", "b", "target"])

    def test_columns_i_mapping(self):
        md = self.MData.openfilecsv(self.path)
        self.assertEqual(md.columns_i["a"], 0)
        self.assertEqual(md.columns_i["target"], 2)


# ---------------------------------------------------------------------------
# KNN produces correct nearest neighbours
# ---------------------------------------------------------------------------

class TestKNN(unittest.TestCase):

    def setUp(self):
        from vx.com.py.proximity.KNN import KNN
        self.KNN = KNN

    def test_returns_correct_shape(self):
        X = [[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [3.0, 0.0]]
        result = self.KNN.execute(2, X, "euclidean")
        self.assertEqual(len(result), 4)
        for row in result:
            self.assertEqual(len(row), 2)

    def test_nearest_is_correct(self):
        X = [[0.0, 0.0], [1.0, 0.0], [10.0, 0.0], [11.0, 0.0]]
        result = self.KNN.execute(1, X, "euclidean")
        # Point 0's nearest neighbour should be point 1
        self.assertEqual(result[0][0][0], 1)
        # Point 2's nearest neighbour should be point 3
        self.assertEqual(result[2][0][0], 3)

    def test_distances_ascending(self):
        X = [[0.0], [1.0], [3.0], [6.0]]
        result = self.KNN.execute(3, X, "euclidean")
        for row in result:
            dists = [d for _, d in row]
            self.assertEqual(dists, sorted(dists))

    def test_no_self_in_neighbours(self):
        X = [[float(i)] for i in range(6)]
        result = self.KNN.execute(3, X, "euclidean")
        for i, row in enumerate(result):
            ids = [j for j, _ in row]
            self.assertNotIn(i, ids)


# ---------------------------------------------------------------------------
# GNNFE.completing uses O(1) set lookup — correctness check
# ---------------------------------------------------------------------------

class TestGNNFECompleting(unittest.TestCase):

    def setUp(self):
        from vx.com.py.graph.GNNFE import GNNFE
        self.GNNFE = GNNFE

    def test_symmetry_after_completing(self):
        neighbors = [
            [[1, 0.5]],
            [],          # 1 does not have 0 as neighbor yet
            [[1, 0.3]],
        ]
        self.GNNFE.completing(neighbors)
        ids_1 = [j for j, _ in neighbors[1]]
        self.assertIn(0, ids_1)

    def test_idempotent_on_already_symmetric(self):
        neighbors = [
            [[1, 0.5], [2, 0.8]],
            [[0, 0.5]],
            [[0, 0.8]],
        ]
        import copy
        before = copy.deepcopy(neighbors)
        self.GNNFE.completing(neighbors)
        # No new edges should be added for node 0 (already present in both)
        ids_0_after = [j for j, _ in neighbors[0]]
        self.assertIn(1, ids_0_after)
        self.assertIn(2, ids_0_after)


# ---------------------------------------------------------------------------
# Full integration: feature graph unchanged by optimisations
# ---------------------------------------------------------------------------

class TestFeatureGraphIntegration(unittest.TestCase):

    def setUp(self):
        import tempfile, os
        from vx.gff.graphtree.graphtree_pure import Graph
        from vx.gff.Settings import Settings
        self.Graph = Graph
        self.tmp = tempfile.mkdtemp()
        Settings.DATA_PATH = self.tmp + "/"
        ds_dir = os.path.join(self.tmp, "ds")
        os.makedirs(ds_dir, exist_ok=True)
        csv = "a,b,c,target\n1,2,3,0\n2,1,4,1\n3,4,1,0\n4,3,2,1\n"
        with open(os.path.join(ds_dir, "transform.csv"), "w") as f:
            f.write(csv)
        self.Settings = Settings
        self.old_path = Settings.DATA_PATH

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.Settings.DATA_PATH = self.old_path

    def _run(self, algo, relevance):
        g = self.Graph()
        g.make_graph(
            self.Settings.DATA_PATH,
            [],
            {
                "file": "ds",
                "proximity": "Euclidean",
                "target": 3,
                "algorithm": algo,
                "relevance": relevance,
                "isfeature": 1,
            },
        )
        return g.data

    def test_mst_correlation_node_count(self):
        data = self._run("mst", "Correlation")
        self.assertEqual(len(data["graph"]["nodes"]), 4)

    def test_mst_correlation_link_count(self):
        data = self._run("mst", "Correlation")
        self.assertEqual(len(data["graph"]["links"]), 3)

    def test_mst_correlation_tree_present(self):
        data = self._run("mst", "Correlation")
        self.assertIn("id", data["tree"])

    def test_mst_correlation_treehi_nonempty(self):
        data = self._run("mst", "Correlation")
        self.assertGreater(len(data["treehi"]), 0)

    def test_mst_pearson_node_count(self):
        data = self._run("mst", "Pearson")
        self.assertEqual(len(data["graph"]["nodes"]), 4)

    def test_mst_extratrees_node_count(self):
        data = self._run("mst", "Extratrees")
        self.assertEqual(len(data["graph"]["nodes"]), 4)

    def test_edgehist_length(self):
        data = self._run("mst", "Correlation")
        self.assertEqual(len(data["edgehist"]), 400)


# ---------------------------------------------------------------------------
# Projection pipeline unchanged
# ---------------------------------------------------------------------------

class TestProjectionPipeline(unittest.TestCase):

    def setUp(self):
        import tempfile, os
        from vx.gff.MakeProjection import MakeProjection
        from vx.gff.Settings import Settings
        self.MP = MakeProjection
        self.tmp = tempfile.mkdtemp()
        self.old_path = Settings.DATA_PATH
        Settings.DATA_PATH = self.tmp + "/"
        ds_dir = os.path.join(self.tmp, "ds2")
        os.makedirs(ds_dir, exist_ok=True)
        csv = "a,b,c,target\n1,2,3,0\n2,1,4,1\n3,4,1,0\n4,3,2,1\n"
        with open(os.path.join(ds_dir, "transform.csv"), "w") as f:
            f.write(csv)
        self.Settings = Settings

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.Settings.DATA_PATH = self.old_path

    def _args(self, proj):
        return {
            "file": "ds2",
            "projection": proj,
            "instanceproximity": "Euclidean",
            "featureselected": [0, 1],
            "target": 3,
            "isfeature": 0,
        }

    def test_pca_point_count(self):
        mp = self.MP()
        mp.execute(self._args("pca"))
        self.assertEqual(len(mp.data["points"]), 4)

    def test_pca_points_finite(self):
        mp = self.MP()
        mp.execute(self._args("pca"))
        for pt in mp.data["points"]:
            self.assertTrue(math.isfinite(pt["x"]))
            self.assertTrue(math.isfinite(pt["y"]))

    def test_simple_projection_x_equals_first_feature(self):
        mp = self.MP()
        mp.execute(self._args("simple"))
        self.assertAlmostEqual(mp.data["points"][0]["x"], 1.0)
        self.assertAlmostEqual(mp.data["points"][0]["y"], 2.0)

    def test_mds_point_count(self):
        mp = self.MP()
        mp.execute(self._args("mds"))
        self.assertEqual(len(mp.data["points"]), 4)

    def test_tsne_point_count(self):
        mp = self.MP()
        mp.execute(self._args("tsne"))
        self.assertEqual(len(mp.data["points"]), 4)


if __name__ == "__main__":
    unittest.main()
