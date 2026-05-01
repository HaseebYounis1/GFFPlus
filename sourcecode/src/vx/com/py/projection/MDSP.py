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
        # self.X = X
        # self.p = p
        super().__init__(X,p)

    def execute(self):
        X = np.asarray(self.X, dtype=float)
        if X.shape[0] == 0:
            return []
        if X.shape[0] == 1:
            return [[0.0, 0.0]]
        mds = MDS(
            n_components=self.p,
            random_state=7,
            n_init=1,
            max_iter=120,
            n_jobs=-1,
            init="random",
        )
        Xt = mds.fit_transform(X)
        X2 = Xt.tolist();
        return X2
