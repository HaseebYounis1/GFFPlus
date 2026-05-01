import numpy as np


class Proximity:
    def __init__(self):
        pass

    @staticmethod
    def compute(a, b, proxtype):
        if proxtype == "euclidean":
            diff = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
            return float(np.sqrt(np.dot(diff, diff)))
        return 0.0


class PMatrix:
    """Symmetric distance cache backed by a numpy upper-triangular matrix."""

    def __init__(self, n):
        self._n = n
        # Use float64; None sentinel replaced by NaN
        self._mat = np.full((n, n), np.nan, dtype=float)

    def get(self, i, j):
        v = self._mat[min(i, j), max(i, j)]
        return None if np.isnan(v) else float(v)

    def set(self, i, j, d):
        self._mat[min(i, j), max(i, j)] = d
            
