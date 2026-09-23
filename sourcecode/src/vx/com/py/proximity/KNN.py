"""Exact nearest neighbours with bounded distance working memory."""
import operator
import numpy as np
from scipy.spatial.distance import cdist


class KNN:
    @staticmethod
    def execute(nneighbors, X, proxtype):
        k = operator.index(nneighbors)
        if k < 0:
            raise ValueError("nneighbors must be nonnegative")
        if proxtype not in ("euclidean", "cosine"):
            raise ValueError("Unsupported neighbour metric: {}".format(proxtype))
        n = len(X)
        if n == 0:
            return []
        arr = np.asarray(X, dtype=float)
        if arr.ndim != 2 or not np.isfinite(arr).all():
            raise ValueError("X must be a finite 2-D matrix")
        k = min(k, n - 1)
        if k == 0:
            return [[] for _ in range(n)]
        result = []
        block = max(1, min(256, 1000000 // n))
        for start in range(0, n, block):
            distances = cdist(arr[start:start + block], arr, metric=proxtype)
            distances = np.nan_to_num(distances, nan=1.0)
            for offset, row in enumerate(distances):
                row[start + offset] = np.inf
                # Stable sorting makes ties deterministic and excludes self even
                # when several observations have identical coordinates.
                ids = np.argsort(row, kind="stable")[:k]
                result.append([[int(j), float(row[j])] for j in ids])
        return result
