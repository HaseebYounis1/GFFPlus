#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Ivar Vargas Belizario
# Copyright (c) 2020
# E-mail: ivar@usp.br

import random

from vx.com.py.clustering.BKmeans import *
from vx.com.py.clustering.BKmeansFE import *

class Sampling:
    # input: smsize, X, type
    # output: ramdoms ids
    @staticmethod
    def execute(X=None, smsize=None, types=None, proxtype="euclidean"):
        smpid = []
        clusterscentroids = None
        if smsize is None or not 0 <= smsize <= len(X):
            raise ValueError("sample size must be between zero and the row count")
        if smsize == 0:
            return [], None
        if types == "submodular":
            from vx.com.py.sampling.Submodular import shortlist
            return shortlist(X, smsize, metric=proxtype), None
        if types == "random":
            smpid = random.Random(7).sample(range(len(X)), smsize)
        elif types == "clusteringmedoids":
            clusters, centroids = BKmeans.execute(X, smsize, proxtype)
            for i in range(len(clusters)):
                cs = clusters[i]
                ce = centroids[i]
                idme = BKmeans.computeMedoid(X, cs, ce, proxtype)
                smpid.append(idme)
            clusterscentroids = (clusters, centroids) 
        else:
            raise ValueError("Unknown sampling method: {}".format(types))
        return smpid, clusterscentroids


    @staticmethod
    def executeFE(X=None, smsize=None, types=None, proxtype=0):
        smpid = []
        clusterscentroids = None
        if smsize is None or not 0 <= smsize <= X.rows():
            raise ValueError("sample size must be between zero and the row count")
        if smsize == 0:
            return [], None
        if types in ("random", "submodular"):
            if types == "submodular" and proxtype not in (0, 5):
                raise ValueError("submodular sampling supports Euclidean and cosine")
            return Sampling.execute(X._data, smsize, types,
                                    "cosine" if proxtype == 5 else "euclidean")
        elif types == "clusteringmedoids":
            clusters, centroids = BKmeansFE.execute(X, smsize, proxtype)
            for clu in clusters:
                cs = clu.cluster
                ce = clu.centroid
                clu.medoid = BKmeansFE.computeMedoid(X, cs, centroids, ce, proxtype)
                smpid.append(clu.medoid)
            clusterscentroids = (clusters, centroids) 
        else:
            raise ValueError("Unknown sampling method: {}".format(types))
        return smpid, clusterscentroids
