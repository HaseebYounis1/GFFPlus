#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Liz M. Huancapaza Hilasaca
# Copyright (c) 2020
# E-mail: lizhh@usp.br

import os
import sys
import warnings

os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 1))
warnings.filterwarnings("ignore", message="Could not find the number of physical cores.*")

import numpy as np
from sklearn.decomposition import PCA
from sklearn.manifold import SpectralEmbedding
from sklearn.preprocessing import normalize

from vx.com.py.projection.Projection import *

class UMAPP(Projection):
    def __init__(self, X=None, p=2, proxtype="euclidean"):
        self.X = X
        self.p = p
        self.proxtype = proxtype
        self.fallback_reason = ""
        super().__init__(X,p)

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

        n_neighbors = min(15, max(2, X.shape[0] - 1))
        if sys.version_info < (3, 13):
            try:
                import umap
                X2 = umap.UMAP(
                    n_components=self.p,
                    metric=self.proxtype,
                    n_neighbors=n_neighbors,
                    n_epochs=120,
                    low_memory=True,
                    random_state=None,
                    n_jobs=-1,
                ).fit_transform(X)
                return X2.tolist();
            except Exception as exc:
                self.fallback_reason = "UMAP failed; spectral/PCA fallback was used: {}".format(str(exc))
                print("UMAP failed; using spectral fallback:", exc)
        else:
            self.fallback_reason = "UMAP is unavailable on this Python version; spectral/PCA fallback was used"

        Xwork = normalize(X) if self.proxtype == "cosine" else X
        try:
            X2 = SpectralEmbedding(
                n_components=self.p,
                n_neighbors=n_neighbors,
                random_state=7,
                affinity="nearest_neighbors",
            ).fit_transform(Xwork)
        except Exception:
            X2 = PCA(n_components=self.p, random_state=7).fit_transform(Xwork)
        return X2.tolist();
