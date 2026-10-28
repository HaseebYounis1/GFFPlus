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

        quality, point_fidelity = self._compute_projection_quality(
            X, X2, yt, target_type=target_type, metric=metric
        )
        self.data["quality"] = quality

        for i in range(N):
            self.data["points"].append({
                "id": int(row_ids[i]),
                "x": float(X2[i][0]),
                "y": float(X2[i][1]),
                "t": float(yt[i]) if target_type == "regression" else int(yt[i]),
                "targetvalue": float(values[i]),
                "fidelity": float(point_fidelity[i]),
            })

        del XDF
        del XR
        del X

    @staticmethod
    def _compute_projection_quality(X_high, X_low, yt=None, target_type="classification", metric="euclidean", k=10):
        X_h = np.asarray(X_high, dtype=np.float64)
        X_l = np.asarray(X_low, dtype=np.float64)
        if X_h.ndim == 1:
            X_h = X_h.reshape(-1, 1)
        if X_l.ndim == 1:
            X_l = X_l.reshape(-1, 1)
        n = X_h.shape[0]
        if n < 4 or X_l.shape[0] != n:
            return {
                "trustworthiness": 1.0,
                "continuity": 1.0,
                "shepard_corr": 1.0,
                "mean_fidelity": 1.0,
                "silhouette": None,
                "k": 0,
            }, np.ones(n, dtype=np.float64)

        X_h = np.nan_to_num(X_h, copy=False)
        X_l = np.nan_to_num(X_l, copy=False)

        k_eff = min(int(k), max(1, n - 2))
        from scipy.spatial.distance import cdist

        # For n <= 1500 compute exact pairwise distances; for larger n compute exact k-NN
        # against a deterministic landmark/evaluation set for global metrics while computing
        # exact k-NN fidelity in batches.
        max_eval = 1200
        if n <= max_eval:
            eval_idx = np.arange(n, dtype=int)
        else:
            rng = np.random.default_rng(7)
            eval_idx = np.sort(rng.choice(n, size=max_eval, replace=False))

        X_h_eval = X_h[eval_idx]
        X_l_eval = X_l[eval_idx]
        m = len(eval_idx)
        k_eval = min(k_eff, max(1, m - 2))

        D_h = cdist(X_h_eval, X_h_eval, metric=metric if metric in ("euclidean", "cosine") else "euclidean")
        D_h = np.nan_to_num(D_h, copy=False)
        np.fill_diagonal(D_h, np.inf)

        D_l = cdist(X_l_eval, X_l_eval, metric="euclidean")
        D_l = np.nan_to_num(D_l, copy=False)
        np.fill_diagonal(D_l, np.inf)

        # Ranks in high-D and low-D (1-indexed, excluding self which is inf at rank m)
        order_h = np.argsort(D_h, axis=1)
        order_l = np.argsort(D_l, axis=1)

        ranks_h = np.empty_like(order_h)
        ranks_l = np.empty_like(order_l)
        row_indices = np.arange(m)[:, None]
        ranks_h[row_indices, order_h] = np.arange(1, m + 1)
        ranks_l[row_indices, order_l] = np.arange(1, m + 1)

        nn_h = order_h[:, :k_eval]
        nn_l = order_l[:, :k_eval]

        # Trustworthiness: points in low-D k-NN that were > k_eval in high-D
        r_h_of_nn_l = ranks_h[row_indices, nn_l]
        t_penalty = np.maximum(0, r_h_of_nn_l - k_eval).sum()

        # Continuity: points in high-D k-NN that are > k_eval in low-D
        r_l_of_nn_h = ranks_l[row_indices, nn_h]
        c_penalty = np.maximum(0, r_l_of_nn_h - k_eval).sum()

        denom = m * k_eval * (2 * m - 3 * k_eval - 1)
        if denom > 0:
            trustworthiness = float(np.clip(1.0 - (2.0 / denom) * t_penalty, 0.0, 1.0))
            continuity = float(np.clip(1.0 - (2.0 / denom) * c_penalty, 0.0, 1.0))
        else:
            trustworthiness = 1.0
            continuity = 1.0

        # Shepard diagram correlation (upper triangle of finite distances)
        tri_u = np.triu_indices(m, k=1)
        d_h_flat = D_h[tri_u]
        d_l_flat = D_l[tri_u]
        if d_h_flat.size > 1 and np.std(d_h_flat) > 1e-12 and np.std(d_l_flat) > 1e-12:
            shepard_corr = float(np.clip(np.corrcoef(d_h_flat, d_l_flat)[0, 1], -1.0, 1.0))
        else:
            shepard_corr = 1.0

        # Pointwise k-NN neighborhood fidelity for all n points
        if n <= max_eval:
            # Vectorized intersection size between nn_h and nn_l per row
            in_high_knn = ranks_h <= k_eval
            in_low_knn = ranks_l <= k_eval
            point_fidelity = (in_high_knn & in_low_knn).sum(axis=1).astype(np.float64) / float(k_eval)
        else:
            # Compute k-NN overlap against evaluation landmarks for large N
            D_h_all = cdist(X_h, X_h_eval, metric=metric if metric in ("euclidean", "cosine") else "euclidean")
            D_l_all = cdist(X_l, X_l_eval, metric="euclidean")
            D_h_all = np.nan_to_num(D_h_all, copy=False)
            D_l_all = np.nan_to_num(D_l_all, copy=False)
            D_h_all[eval_idx, np.arange(m)] = np.inf
            D_l_all[eval_idx, np.arange(m)] = np.inf
            top_h = np.argpartition(D_h_all, kth=k_eval - 1, axis=1)[:, :k_eval]
            top_l = np.argpartition(D_l_all, kth=k_eval - 1, axis=1)[:, :k_eval]
            mask_h = np.zeros((n, m), dtype=bool)
            mask_l = np.zeros((n, m), dtype=bool)
            rows_all = np.arange(n)[:, None]
            mask_h[rows_all, top_h] = True
            mask_l[rows_all, top_l] = True
            point_fidelity = (mask_h & mask_l).sum(axis=1).astype(np.float64) / float(k_eval)

        point_fidelity = np.clip(point_fidelity, 0.0, 1.0)

        silhouette_val = None
        if yt is not None and target_type == "classification":
            y_arr = np.asarray(yt)
            uniq = np.unique(y_arr)
            if 2 <= len(uniq) < n:
                try:
                    from vx.gff.graphtree.graphtree_pure import Metrics
                    z = {int(u): idx for idx, u in enumerate(uniq)}
                    silhouette_val = float(Metrics.compute_silhoute(X_l, y_arr.astype(int), z))
                except Exception:
                    silhouette_val = None

        return {
            "trustworthiness": round(trustworthiness, 4),
            "continuity": round(continuity, 4),
            "shepard_corr": round(shepard_corr, 4),
            "mean_fidelity": round(float(np.mean(point_fidelity)), 4),
            "silhouette": round(silhouette_val, 4) if silhouette_val is not None else None,
            "k": int(k_eval),
        }, point_fidelity

    @staticmethod
    def preview_perturbation(argms):
        """
        Compute a fast Procrustes-aligned what-if subspace perturbation preview
        ('Ghost Trails') showing how projected instances move when a candidate
        feature is added to or removed from the active feature subspace.
        """
        from scipy.linalg import orthogonal_procrustes
        from vx.com.py.projection.PCAP import PCAP

        file_id = str(argms["file"])
        filefepath = Settings.DATA_PATH + file_id + "/"
        filefe = filefepath + "transform.csv"
        targeti = int(argms.get("target", 0))
        projprox = argms.get("instanceproximity", "DEuclidean")
        metric = "cosine" if projprox == "DCosine" else "euclidean"

        base_features = []
        seen = set()
        for idx in argms.get("featureselected", []):
            try:
                val = int(idx)
            except (TypeError, ValueError):
                continue
            if val != targeti and val not in seen:
                base_features.append(val)
                seen.add(val)

        candidate_raw = argms.get("candidate_feature", argms.get("candidate_features", []))
        if isinstance(candidate_raw, (int, float, str)):
            candidates = [int(candidate_raw)] if str(candidate_raw).strip() != "" else []
        else:
            candidates = [int(c) for c in candidate_raw if str(c).strip() != ""]
        candidates = [c for c in candidates if c != targeti]

        action = str(argms.get("action", "toggle")).lower()

        XDF = DataMatrix(filefe, max_rows=5000, dtype=np.float64)
        colsindexes = XDF.columnsindexes()
        colsnameslist = XDF.columns_index()
        trueids = XDF.trueids()

        targeti_true = trueids[targeti] if 0 <= targeti < len(trueids) else -1
        all_non_target = [i for _, i in colsindexes.items() if i != targeti_true]

        if not base_features:
            # If no explicit subset was selected, base is all non-target columns
            inv_true = {local_i: orig_i for orig_i, local_i in enumerate(trueids) if local_i >= 0}
            base_features = [inv_true[i] for i in all_non_target if i in inv_true]

        perturbed_features = list(base_features)
        applied_action = "add"
        for c in candidates:
            if action == "remove" or (action == "toggle" and c in perturbed_features):
                if len(perturbed_features) > 1 and c in perturbed_features:
                    perturbed_features.remove(c)
                    applied_action = "remove"
            else:
                if c not in perturbed_features:
                    perturbed_features.append(c)
                    applied_action = "add"

        local_base = [trueids[i] for i in base_features if 0 <= i < len(trueids) and trueids[i] >= 0]
        local_pert = [trueids[i] for i in perturbed_features if 0 <= i < len(trueids) and trueids[i] >= 0]
        if not local_base:
            local_base = all_non_target
        if not local_pert:
            local_pert = local_base

        X_base = XDF.selectcolumns_index(local_base)._data
        X_pert = XDF.selectcolumns_index(local_pert)._data
        yt = XDF.getcolumn_array(targeti_true, copy=True).astype(np.float64, copy=False) if targeti_true >= 0 else np.zeros(X_base.shape[0])
        local_ids = XDF._row_ids
        row_ids = source_ids(filefepath, local_ids)

        target_type = argms.get("targettype")
        if target_type not in ("regression", "classification"):
            target_type = "regression" if type_of_target(yt) == "continuous" else "classification"
        if target_type == "classification":
            _, yt_codes = np.unique(yt, return_inverse=True)
        else:
            yt_codes = yt

        Y_base = np.asarray(PCAP(X_base).execute(), dtype=np.float64)
        Y_pert = np.asarray(PCAP(X_pert).execute(), dtype=np.float64)

        # Orthogonal Procrustes alignment so Y_pert is oriented & scaled consistently with Y_base
        mu_b = Y_base.mean(axis=0, keepdims=True)
        mu_p = Y_pert.mean(axis=0, keepdims=True)
        Yc_b = Y_base - mu_b
        Yc_p = Y_pert - mu_p
        norm_b = float(np.linalg.norm(Yc_b))
        norm_p = float(np.linalg.norm(Yc_p))
        if norm_b > 1e-12 and norm_p > 1e-12:
            R, _ = orthogonal_procrustes(Yc_p / norm_p, Yc_b / norm_b)
            Y_pert_aligned = (Yc_p / norm_p) @ R * norm_b + mu_b
        else:
            Y_pert_aligned = Y_pert.copy()

        qual_before, fid_before = MakeProjection._compute_projection_quality(
            X_base, Y_base, yt_codes, target_type=target_type, metric=metric
        )
        qual_after, fid_after = MakeProjection._compute_projection_quality(
            X_pert, Y_pert_aligned, yt_codes, target_type=target_type, metric=metric
        )

        # Normalize both layouts into the same [0, 1] bounding box for direct visual overlay
        combined = np.vstack([Y_base, Y_pert_aligned])
        mins = combined.min(axis=0)
        maxs = combined.max(axis=0)
        spans = np.where((maxs - mins) > 1e-12, maxs - mins, 1.0)
        Yb_norm = (Y_base - mins) / spans
        Yp_norm = (Y_pert_aligned - mins) / spans
        deltas = Yp_norm - Yb_norm
        mags = np.hypot(deltas[:, 0], deltas[:, 1])

        trails = []
        for i in range(len(row_ids)):
            trails.append({
                "id": int(row_ids[i]),
                "x1": round(float(Yb_norm[i, 0]), 5),
                "y1": round(float(Yb_norm[i, 1]), 5),
                "x2": round(float(Yp_norm[i, 0]), 5),
                "y2": round(float(Yp_norm[i, 1]), 5),
                "dx": round(float(deltas[i, 0]), 5),
                "dy": round(float(deltas[i, 1]), 5),
                "displacement": round(float(mags[i]), 5),
                "fidelity_before": round(float(fid_before[i]), 4),
                "fidelity_after": round(float(fid_after[i]), 4),
            })

        cand_names = [
            colsnameslist[trueids[c]]
            for c in candidates
            if 0 <= c < len(trueids) and trueids[c] >= 0
        ]

        return {
            "status": "ok",
            "action": applied_action,
            "candidates": candidates,
            "candidate_names": cand_names,
            "base_feature_count": len(base_features),
            "perturbed_feature_count": len(perturbed_features),
            "perturbed_features": perturbed_features,
            "quality_before": qual_before,
            "quality_after": qual_after,
            "quality_delta": {
                "trustworthiness": round(qual_after["trustworthiness"] - qual_before["trustworthiness"], 4),
                "continuity": round(qual_after["continuity"] - qual_before["continuity"], 4),
                "shepard_corr": round(qual_after["shepard_corr"] - qual_before["shepard_corr"], 4),
                "mean_fidelity": round(qual_after["mean_fidelity"] - qual_before["mean_fidelity"], 4),
                "silhouette": (
                    round(qual_after["silhouette"] - qual_before["silhouette"], 4)
                    if qual_after["silhouette"] is not None and qual_before["silhouette"] is not None
                    else None
                ),
            },
            "mean_displacement": round(float(np.mean(mags)) if len(mags) else 0.0, 5),
            "trails": trails,
        }

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
