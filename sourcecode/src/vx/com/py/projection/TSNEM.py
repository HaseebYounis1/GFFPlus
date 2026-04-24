#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Liz M. Huancapaza Hilasaca
# Copyright (c) 2020
# E-mail: lizhh@usp.br

import os
import warnings

os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 1))
warnings.filterwarnings("ignore", message="Could not find the number of physical cores.*")

import numpy as np

from sklearn.manifold import TSNE


from vx.com.py.projection.Projection import *

class TSNEM(Projection):
    def __init__(self, X=None, p=2, proxtype="euclidean"):
        self.proxtype = proxtype
        super().__init__(X,p)

    def execute(self):
        X = np.asarray(self.X, dtype=float)
        if X.shape[0] == 0:
            return []
        if X.shape[0] == 1:
            return [[0.0, 0.0]]

        perplexity = min(30, max(1, (X.shape[0] - 1) // 3))
        X2 = TSNE(
            metric=self.proxtype,
            n_components=self.p,
            random_state=7,
            perplexity=perplexity,
            init="random" if self.proxtype == "cosine" else "pca",
            learning_rate="auto",
        ).fit_transform(X)
        return X2.tolist();
        
