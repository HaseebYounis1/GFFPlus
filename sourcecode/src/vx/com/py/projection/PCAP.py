#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Liz M. Huancapaza Hilasaca
# Copyright (c) 2020
# E-mail: lizhh@usp.br


import numpy as np

#from sklearn.manifold import PCA
from sklearn.decomposition import PCA

from vx.com.py.projection.Projection import *

class PCAP(Projection):
    def __init__(self, X=None, p=2):
        # self.X = X
        # self.p = p
        super().__init__(X, p)

    def execute(self):
        X = np.asarray(self.X, dtype=np.float32)
        if X.ndim == 1:
            X = X.reshape((-1, 1))
        if X.shape[0] == 0:
            return []
        if X.shape[0] == 1:
            return [[0.0, 0.0]]
        if X.shape[1] == 0:
            return np.zeros((X.shape[0], 2), dtype=float).tolist()
        if not np.isfinite(X).all():
            X = np.nan_to_num(X, copy=False)
        if not np.any(np.var(X, axis=0) > 0.0):
            return np.zeros((X.shape[0], 2), dtype=float).tolist()

        components = min(self.p, X.shape[0], X.shape[1])
        pca = PCA(n_components=components, svd_solver='randomized', random_state=7)
        pca.fit(X)
        X2 = pca.transform(X)
        if components == 1:
            X2 = np.column_stack([X2[:, 0], np.zeros(X2.shape[0])])
        return X2.tolist()
        
