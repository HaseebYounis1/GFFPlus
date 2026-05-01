import numpy as np
from time import process_time

from vx.com.py.proximity.Proximity import *

class KNNFE:

    def __init__(self):
        pass

    @staticmethod
    def execute(nneighbors, clusters, X, proxtype):
        start = process_time()
        n = len(clusters)
        if n == 0:
            return []

        centroid_ids = [c.centroid for c in clusters]
        cent_data = X._data[centroid_ids, :]  # (n_clusters, features)

        # Vectorised pairwise Euclidean between centroids
        sq = (cent_data ** 2).sum(axis=1)
        dots = cent_data @ cent_data.T
        dist_matrix = np.sqrt(np.maximum(sq[:, None] + sq[None, :] - 2.0 * dots, 0.0))

        k = min(nneighbors, n - 1)
        ner = []
        for i in range(n):
            row = dist_matrix[i]
            # argpartition gives cheapest k+1 indices (includes self)
            idx = np.argpartition(row, min(k, n - 1))[:k + 1]
            idx = idx[idx != i][:k]
            idx = idx[np.argsort(row[idx])]
            ner.append([[int(j), float(row[j])] for j in idx])

        end = process_time()
        print("time KNNFE: {:.5f}".format(end - start))
        return ner


