import heapq
import numpy as np
from time import process_time

from vx.com.py.proximity.Proximity import *

class KNN:

    def __init__(self):
        pass

    @staticmethod
    def execute(nneighbors, X, proxtype):
        start = process_time()
        n = len(X)
        if n == 0:
            return []

        arr = np.asarray(X, dtype=float)
        # Vectorised pairwise Euclidean (only metric currently used)
        if proxtype == "euclidean":
            sq = (arr ** 2).sum(axis=1)
            dots = arr @ arr.T
            sq_dists = np.maximum(sq[:, None] + sq[None, :] - 2.0 * dots, 0.0)
            dist_matrix = np.sqrt(sq_dists)
        else:
            dist_matrix = np.zeros((n, n), dtype=float)
            for i in range(n):
                for j in range(i + 1, n):
                    d = Proximity.compute(X[i], X[j], proxtype)
                    dist_matrix[i, j] = d
                    dist_matrix[j, i] = d

        k = min(nneighbors, n - 1)
        ner = []
        for i in range(n):
            row = dist_matrix[i]
            idx = np.argpartition(row, range(1, k + 1))[:k + 1]
            idx = idx[idx != i][:k]
            idx = idx[np.argsort(row[idx])]
            ner.append([[int(j), float(row[j])] for j in idx])

        end = process_time()
        print("time KNN: {:.5f}".format(end - start))
        return ner


