import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
from scipy.spatial.distance import cdist

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sourcecode" / "src"))
from vx.com.py.sampling.Submodular import shortlist
from vx.com.py.sampling.Sampling import Sampling
from vx.com.py.clustering.BKmeans import BKmeans
from vx.com.py.clustering.BKmeansFE import BKmeansFE
from vx.com.px.dataset.dataio_pure import DataMatrix
from vx.com.py.proximity.KNN import KNN


class ShortlistingTests(unittest.TestCase):
    def test_exact_greedy_matches_independent_dense_reference(self):
        X = np.random.default_rng(3).normal(size=(18, 4))
        similarities = 1 / (1 + cdist(X, X))
        chosen = []
        for selected in shortlist(X, 6, epsilon=0, batch_size=3):
            scores = [(-1 if j in chosen else similarities[:, chosen + [j]].max(axis=1).sum())
                      for j in range(len(X))]
            # Equivalent gains may tie at floating-point precision.
            self.assertAlmostEqual(scores[selected], max(scores), places=12)
            chosen.append(selected)

    def test_unique_reproducible_and_bounded_distance_blocks(self):
        X = np.random.default_rng(1).normal(size=(400, 5))
        with patch("vx.com.py.sampling.Submodular.cdist", wraps=cdist) as distance:
            ids = shortlist(X, 20, max_reference=23, batch_size=9)
            self.assertTrue(all(call.args[0].shape[0] <= 9 and call.args[1].shape[0] <= 23
                                for call in distance.call_args_list))
        self.assertEqual(len(set(ids)), 20)
        self.assertEqual(ids, shortlist(X, 20, max_reference=23, batch_size=9))

    def test_edge_cases(self):
        self.assertEqual(shortlist(np.empty((0, 2)), 0), [])
        self.assertEqual(shortlist(np.zeros((6, 2)), 3, epsilon=0), [0, 1, 2])
        self.assertEqual(len(shortlist(np.zeros((6, 2)), 3, metric="cosine")), 3)
        for size in (-1, 7, 1.5):
            with self.assertRaises((TypeError, ValueError)):
                shortlist(np.zeros((6, 2)), size)
        with self.assertRaises(ValueError):
            shortlist([[np.nan]], 1)

    def test_cluster_coverage(self):
        X = np.array([[0.0], [0.1], [0.2], [100.0], [100.1], [100.2]])
        ids = shortlist(X, 2, epsilon=0)
        self.assertEqual({int(X[i, 0] > 50) for i in ids}, {0, 1})

    def test_sampling_zero_and_fe_random(self):
        X = DataMatrix()
        X._data = np.arange(12).reshape(6, 2)
        self.assertEqual(Sampling.execute(X._data, 0, "random"), ([], None))
        self.assertEqual(len(Sampling.executeFE(X, 3, "random")[0]), 3)
        self.assertEqual(len(Sampling.executeFE(X, 3, "submodular")[0]), 3)

    def test_clustering_impossible_sizes_and_single_centroid(self):
        X = DataMatrix()
        X._data = np.array([[0.0], [10.0]])
        for k in (0, 3):
            with self.assertRaises(ValueError):
                BKmeans.execute(X._data, k)
            with self.assertRaises(ValueError):
                BKmeansFE.execute(X, k)
        self.assertEqual(BKmeans.execute(X._data, 1)[1], [[5.0]])
        _, centroids = BKmeansFE.execute(X, 1)
        self.assertEqual(centroids._data[0, 0], 5)

    def test_knn_large_offset_and_duplicates(self):
        X = [[1e12], [1e12 + 1], [1e12 + 3]]
        self.assertEqual(KNN.execute(1, X, "euclidean")[0], [[1, 1.0]])
        for i, neighbors in enumerate(KNN.execute(3, [[0]] * 5, "euclidean")):
            self.assertEqual(len(neighbors), 3)
            self.assertNotIn(i, [j for j, _ in neighbors])
        with self.assertRaises(ValueError):
            KNN.execute(-1, X, "euclidean")

    def test_mds_distances_preserve_small_differences(self):
        from vx.com.py.projection.MDSP import MDSP
        with patch("vx.com.py.projection.MDSP.MDS") as estimator:
            estimator.return_value.fit_transform.return_value = np.zeros((3, 2))
            MDSP([[1e12], [1e12 + 1], [1e12 + 3]]).execute()
            distances = estimator.return_value.fit_transform.call_args.args[0]
            np.testing.assert_allclose(distances, [[0, 1, 3], [1, 0, 2], [3, 2, 0]])

    def test_umap_fallback_single_feature(self):
        from vx.com.py.projection.UMAPP import UMAPP
        with patch("vx.com.py.projection.UMAPP.sys.version_info", (3, 13)), \
             patch("vx.com.py.projection.UMAPP.SpectralEmbedding", side_effect=ValueError):
            projector = UMAPP([[0], [1]])
            self.assertEqual(np.asarray(projector.execute()).shape, (2, 2))
            self.assertEqual(projector.projection_used, "pca")

    def test_xai_handles_infinity_without_nan(self):
        import pandas as pd
        from vx.gff.XAI import XAIPipeline
        frame = pd.DataFrame({"a": [np.inf, 2, 3], "target": [0, 1, np.inf]})
        X, y = XAIPipeline()._prepare_arrays(frame, frame.columns, [0], 1)
        self.assertTrue(np.isfinite(X).all())
        self.assertEqual(y.tolist(), [0, 1])

    def test_projection_keeps_original_ids_labels_and_resets(self):
        from vx.gff.MakeProjection import MakeProjection
        from vx.gff.Settings import Settings
        with tempfile.TemporaryDirectory() as tmp:
            ds = Path(tmp) / "ds"
            ds.mkdir()
            (ds / "transform.csv").write_text("a,b,target\n0,0,0\n1,2,1\n3,6,0\n10,20,1\n")
            (ds / "original.csv").write_text("a,b,target\n0,0,cat\n1,2,dog\n3,6,cat\n10,20,dog\n")
            args = dict(file="ds", target=2, featureselected=[0, 1], projection="simple",
                        instanceproximity="Euclidean", submodular_size=2)
            with patch.object(Settings, "DATA_PATH", tmp + "/"):
                projector = MakeProjection()
                projector.execute(args)
                for point in projector.data["points"]:
                    self.assertEqual(point["x"], [0, 1, 3, 10][point["id"]])
                    self.assertEqual(projector.data["tartegsnames"][point["t"]],
                                     ["cat", "dog", "cat", "dog"][point["id"]])
                args.pop("submodular_size")
                projector.execute(args)
                self.assertEqual(len(projector.data["points"]), 4)
                self.assertNotIn("sampling", projector.data)


if __name__ == "__main__":
    unittest.main()
