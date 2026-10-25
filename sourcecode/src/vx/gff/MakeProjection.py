#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Ivar Vargas Belizario
# Copyright (c) 2020
# E-mail: ivar@usp.br

from vx.gff.Settings import *

import os
import sys
import importlib.util
import warnings
from time import process_time
from vx.gff.Ingestion import source_ids, sampling_metadata
from vx.com.py.sampling.CSVSample import read_rows
from sklearn.utils.multiclass import type_of_target

import numpy as np
import pandas as pd

os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 1))
warnings.filterwarnings("ignore", message="Could not find the number of physical cores.*")

from vx.com.px.dataset.dataio_pure import DataMatrix, ProximityMatrix

from vx.com.py.matrix.CSVData import *





class MakeProjection():
    MAX_EXACT_TSNE_ROWS = 3000
    MAX_EXACT_MDS_ROWS = 2000
    MAX_EXACT_UMAP_ROWS = 20000

    def __init__(self):
        self.data = {"points":[],"tartegscolors":[],"tartegsnames":{}}

    def execute(self, argms):
        self.data = {"points": [], "tartegscolors": [], "tartegsnames": {}}
        mt = argms["projection"]
        projprox = argms["instanceproximity"]

        targeti = int(argms["target"])
        featureselected = []
        seen_features = set()
        for index in argms.get("featureselected", []):
            try:
                index = int(index)
            except (TypeError, ValueError):
                continue
            if index != targeti and index not in seen_features:
                featureselected.append(index)
                seen_features.add(index)
        filefepath = Settings.DATA_PATH+argms["file"]+"/"
        filefe = filefepath+"transform.csv"

        # df = pd.read_csv(filefe)
        # dmat = MData.openfilecsv(filefe)
        
        # get only name without target
        # fenames = []
        # for c in dmat.columns_index():
        #     if c != target:
        #         fenames.append(c)
        # X = []
        # if len(featureselected)>0:
        #     sel = []
        #     for s,v in featureselected.items():
        #         sel.append(s)
        #     #print("dmat.cat_columns_i",dmat.columns,dmat.columns_i)
        #     #print("dmat.getData()",dmat.getData())
        #     #print("selselselselselselselselselselselselselsel", sel)
        #     X = dmat.sample(smp_cols=sel).getData()
        # else:
        #     X = dmat.sample(smp_cols=fenames).getData()

        start = process_time()
        selected_load_ids = None
        if featureselected:
            selected_load_ids = featureselected + [targeti]
        XDF = DataMatrix(filefe, selectedfeids=selected_load_ids, max_rows=5000, dtype=np.float64)
        #target_index = XDF.columnindex(target)

        colsindexes = XDF.columnsindexes()
        colsnameslist = XDF.columns_index()
        trueids = XDF.trueids()
        
        targeti_true = trueids[targeti] if 0 <= targeti < len(trueids) else -1
        if targeti_true < 0:
            raise ValueError("Target column {} is not available in {}".format(targeti, filefe))
        target = colsnameslist[targeti_true]

        fenames = []
        for name, i in colsindexes.items():
            if i != targeti_true:
                fenames.append(i)

        XR = None
        if len(featureselected)>0:
            local_features = [
                trueids[index] for index in featureselected
                if 0 <= index < len(trueids) and trueids[index] >= 0
            ]
            XR = XDF.selectcolumns_index(local_features)
        else:
            XR = XDF.selectcolumns_index(fenames)
        yt = XDF.getcolumn_array(targeti_true, copy=True).astype(np.float64, copy=False)
        X = XR._data
        end = process_time()

        #y = dmat.sample(smp_cols=[target]).getData()

        if not np.isfinite(yt).all():
            raise ValueError("Target contains missing or nonfinite values")
        local_ids = XDF._row_ids
        row_ids = source_ids(filefepath, local_ids)
        metadata = sampling_metadata(filefepath)
        original_rows = metadata.get("original_rows", XDF._total_rows)
        sample_size = argms.get("submodular_size")
        if sample_size not in (None, ""):
            from vx.com.py.sampling.Submodular import shortlist
            selected = np.asarray(shortlist(X, min(int(sample_size), len(X)),
                                           metric="cosine" if projprox == "DCosine" else "euclidean"), dtype=int)
            row_ids = row_ids[selected]
            local_ids = local_ids[selected]
            X, yt = X[selected], yt[selected]
            XR = XR.selectrows(selected.tolist())
        if metadata or sample_size not in (None, "") or original_rows > len(X):
            self.data["sampling"] = {"method": metadata.get("method", "uniform_reservoir"),
                                     "original_rows": original_rows, "selected_rows": len(X), "seed": 7}
        N = X.shape[0]

        X2 = []

        metric = "cosine" if projprox == "DCosine" else "euclidean"
        requested_mt = mt
        projection_used = mt
        fallback_reason = ""
        if mt == "tsne" and N > MakeProjection.MAX_EXACT_TSNE_ROWS:
            mt = "pca"
            projection_used = "pca"
            fallback_reason = (
                "t-SNE is limited to {} rows in adaptive CPU mode; PCA was used instead"
                .format(MakeProjection.MAX_EXACT_TSNE_ROWS)
            )
        elif mt == "mds" and N > MakeProjection.MAX_EXACT_MDS_ROWS:
            mt = "pca"
            projection_used = "pca"
            fallback_reason = (
                "MDS is limited to {} rows in adaptive CPU mode; PCA was used instead"
                .format(MakeProjection.MAX_EXACT_MDS_ROWS)
            )
        elif mt == "umap" and N > MakeProjection.MAX_EXACT_UMAP_ROWS:
            mt = "pca"
            projection_used = "pca"
            fallback_reason = (
                "UMAP is limited to {} rows in adaptive CPU mode; PCA was used instead"
                .format(MakeProjection.MAX_EXACT_UMAP_ROWS)
            )
        elif mt == "umap" and (
                sys.version_info >= (3, 13) or importlib.util.find_spec("umap") is None
        ):
            projection_used = "spectral"
            fallback_reason = "UMAP is unavailable in this Python environment; spectral/PCA fallback was used"

        try:
            if mt == "tsne":
                from vx.com.py.projection.TSNEM import TSNEM
                X2 = TSNEM(X, proxtype=metric).execute();
            elif mt == "umap":
                from vx.com.py.projection.UMAPP import UMAPP
                projector = UMAPP(X, proxtype=metric)
                X2 = projector.execute();
                if projector.fallback_reason:
                    projection_used = projector.projection_used
                    if not fallback_reason:
                        fallback_reason = projector.fallback_reason
            elif mt == "mds":
                from vx.com.py.projection.MDSP import MDSP
                X2 = MDSP(X).execute();
            elif mt == "pca":
                from vx.com.py.projection.PCAP import PCAP
                X2 = PCAP(X).execute();
            # elif mt == "isomap":
            #     X2 = ISOMAPP(X).execute();
            # elif mt == "fastmap":
            #     X2 = FASTMAPP(X).execute();
            # elif mt == "lspmds":
            #     X2 = LSP(X, smpprj=MDSP(), smptype="clusteringmedoids").execute()
            elif mt == "lsptsne":
                from vx.com.py.projection.LSPU import LSPU
                from vx.com.py.projection.TSNEM import TSNEM
                X2 = LSPU(  X=XR,
                            smpprj=TSNEM(proxtype=metric),
                            proxtype=ProximityMatrix.POT[projprox],
                            smptype="clusteringmedoids"
                        ).execute()
            else:
                X2 = self._pair_projection(X)
        except Exception as exc:
            if mt == "pca":
                raise
            from vx.com.py.projection.PCAP import PCAP
            X2 = PCAP(X).execute()
            projection_used = "pca"
            fallback_reason = "{} failed ({}); PCA was used instead".format(
                requested_mt.upper(),
                str(exc)
            )

        self.data["projectionrequested"] = requested_mt
        self.data["projectionused"] = projection_used
        if fallback_reason:
            self.data["projectionfallback"] = fallback_reason
            
        # elif mt == "lspisomap":
        #     X2 = LSP(X, smpprj=ISOMAPP(), smptype="clusteringmedoids").execute()
        # elif mt == "lspfastmap":
        #     X2 = LSP(X, smpprj=FASTMAPP(), smptype="clusteringmedoids").execute()
        # elif mt == "lspumap":
        #     X2 = LSP(X, smpprj=UMAPP(), smptype="clusteringmedoids").execute()


        target_type = argms.get("targettype")
        if target_type not in ("regression", "classification"):
            target_type = "regression" if type_of_target(yt) == "continuous" else "classification"
        values = yt.copy()
        targetsnames = {}
        if target_type == "classification":
            categories, yt = np.unique(yt, return_inverse=True)
            targetsnames = {i: str(value) for i, value in enumerate(categories)}
            working = filefepath + "working.csv"
            original = filefepath + "original.csv"
            if os.path.isfile(working):
                labels = read_rows(working, local_ids, usecols=[targeti])
            elif os.path.isfile(original):
                labels = read_rows(original, row_ids, usecols=[targeti])
            else:
                labels = None
            if labels is not None:
                for code, label in zip(yt, labels):
                    targetsnames[int(code)] = label[0]
        self.data["targettype"] = target_type
        self.data["targetrange"] = [float(values.min()), float(values.max())] if len(values) else [0, 0]
        self.data["tartegsnames"] = targetsnames

        for i in range(N):
            self.data["points"].append({
                "id": int(row_ids[i]),
                "x": float(X2[i][0]),
                "y": float(X2[i][1]),
                "t": float(yt[i]) if target_type == "regression" else int(yt[i]),
                "targetvalue": float(values[i]),
            })

        del XDF
        del XR
        del X

    @staticmethod
    def _pair_projection(X):
        data = np.asarray(X, dtype=float)
        if data.ndim != 2 or data.shape[0] == 0:
            return []
        if data.shape[1] == 0:
            return np.zeros((data.shape[0], 2), dtype=float).tolist()
        if data.shape[1] == 1:
            return np.column_stack([data[:, 0], np.zeros(data.shape[0])]).tolist()
        return data[:, :2].tolist()
