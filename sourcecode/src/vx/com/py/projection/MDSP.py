#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Liz M. Huancapaza Hilasaca
# Copyright (c) 2020
# E-mail: lizhh@usp.br

import numpy as np
from sklearn.manifold import MDS

from vx.com.py.projection.Projection import *


class MDSP(Projection):
    def __init__(self, X=None, p=2):
        super().__init__(X, p)

    def execute(self):
        X = np.asarray(self.X, dtype=np.float32)
        if X.ndim == 1:
            X = X.reshape((-1, 1))
        n = X.shape[0]

        if n == 0:
            return []
        if n == 1:
            return [[0.0, 0.0]]
        if X.shape[1] == 0:
            return np.zeros((n, 2), dtype=float).tolist()
        if not np.isfinite(X).all():
            X = np.nan_to_num(X, copy=False)

        # Precompute the full Euclidean distance matrix with a single BLAS
        # matrix multiply — avoids sklearn recomputing distances internally.
        sq = (X ** 2).sum(axis=1)
        D  = np.sqrt(np.maximum(sq[:, None] + sq[None, :] - 2.0 * (X @ X.T), 0.0))
        np.fill_diagonal(D, 0.0)
        if not np.any(D):
            return np.zeros((n, 2), dtype=float).tolist()

        mds_kw = dict(
            n_components=self.p,
            dissimilarity="precomputed",  # hand sklearn the pre-built matrix
            random_state=7,
            n_init=1,
            max_iter=300,                 # enough room to converge
            eps=1e-3,                     # visual precision; 1e-9 default is overkill
            n_jobs=1,
        )
        # normalized_stress was added in sklearn 1.4; ignore on older installs
        try:
            mds = MDS(**mds_kw, normalized_stress="auto")
        except TypeError:
            mds = MDS(**mds_kw)

        Xt = mds.fit_transform(D)
        return Xt.tolist()
