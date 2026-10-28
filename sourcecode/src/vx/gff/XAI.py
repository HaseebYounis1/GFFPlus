#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor
from sklearn.inspection import permutation_importance
from sklearn.utils.multiclass import type_of_target
from sklearn.model_selection import train_test_split
from vx.com.py.sampling.CSVSample import sample_csv


RANDOM_STATE = 42


@dataclass
class CPUPlan:
    total_rows: int
    total_features: int
    train_rows: int
    permutation_rows: int
    permutation_repeats: int
    shap_rows: int
    estimators: int
    available_memory_mb: Optional[float]
    n_jobs: int
    mode: str

    def as_dict(self):
        return {
            "total_rows": self.total_rows,
            "total_features": self.total_features,
            "train_rows": self.train_rows,
            "permutation_rows": self.permutation_rows,
            "permutation_repeats": self.permutation_repeats,
            "shap_rows": self.shap_rows,
            "estimators": self.estimators,
            "available_memory_mb": self.available_memory_mb,
            "n_jobs": self.n_jobs,
            "mode": self.mode,
        }


class XAIPipeline:
    """Local, CPU-first XAI pipeline for uploaded tabular datasets."""

    def __init__(self, random_state=RANDOM_STATE):
        self.random_state = int(random_state)
        self.rng = np.random.default_rng(self.random_state)

    def execute(self, data_path, argms, feature_names=None, unselectedfeids=None):
        dataset_id = str(argms["file"])
        csv_path = os.path.join(data_path, dataset_id, "transform.csv")
        if not os.path.exists(csv_path):
            raise FileNotFoundError("transform.csv was not found for dataset {}".format(dataset_id))

        header = pd.read_csv(csv_path, nrows=0, encoding="utf-8-sig").columns
        columns = [str(col).strip() for col in header]
        if feature_names and len(feature_names) == len(columns):
            columns = [str(col).strip() for col in feature_names]

        target_id = _target_id_arg(argms.get("target"), len(columns) - 1)
        if target_id < 0 or target_id >= len(columns):
            raise ValueError("Invalid target column id: {}".format(target_id))

        unselected = {int(i) for i in (unselectedfeids or []) if _is_int_like(i)}
        feature_ids = [
            index for index in range(len(columns))
            if index != target_id and index not in unselected
        ]
        if not feature_ids:
            raise ValueError("No feature columns are available for XAI.")

        total_rows = max(0, _count_csv_rows(csv_path))
        plan = self._make_cpu_plan(total_rows, len(feature_ids), argms)
        frame = self._read_training_frame(csv_path, header, feature_ids, target_id, plan.train_rows)
        X, y = self._prepare_arrays(frame, header, feature_ids, target_id, impute=False)

        if X.shape[0] < 2:
            raise ValueError("XAI needs at least two valid data rows after loading.")

        task_type = argms.get("targettype")
        if task_type not in ("regression", "classification"):
            task_type = self._infer_task_type(y)
        if task_type == "classification" and np.unique(y).size < 2:
            raise ValueError("Classification XAI needs at least two target classes.")

        train, evaluation = self._evaluation_split(y, task_type)
        # Learn missing-value replacements from the training partition only.
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            medians = np.nanmedian(X[train], axis=0)
        medians = np.where(np.isfinite(medians), medians, 0.0)
        X = np.where(np.isfinite(X), X, medians)
        model = self._fit_model(X[train], y[train], task_type, plan)
        importance = _finite_vector(getattr(model, "feature_importances_", np.zeros(X.shape[1])))
        importance_norm = _normalize_nonnegative(importance)

        permutation, permutation_norm, permutation_status = self._compute_permutation(
            model, X[evaluation], y[evaluation], plan
        )
        shap_payload = self._compute_shap(model, X, feature_ids, columns, plan, argms)

        features = []
        shap_norm = np.asarray(shap_payload.get("values_norm", []), dtype=float)
        shap_values = np.asarray(shap_payload.get("values", []), dtype=float)
        for local_index, feature_id in enumerate(feature_ids):
            row = {
                "id": int(feature_id),
                "name": columns[feature_id],
                "importance": float(importance[local_index]),
                "importance_norm": float(importance_norm[local_index]),
                "permutation": float(permutation[local_index]),
                "permutation_norm": float(permutation_norm[local_index]),
            }
            if shap_payload.get("available"):
                row["shap"] = float(shap_values[local_index])
                row["shap_norm"] = float(shap_norm[local_index])
            features.append(row)

        ranking = [
            int(feature_ids[index])
            for index in np.argsort(-importance_norm)
        ]

        return {
            "status": "ok",
            "target": {
                "id": int(target_id),
                "name": columns[target_id],
                "type": task_type,
            },
            "model": {
                "type": model.__class__.__name__,
                "random_state": self.random_state,
                "n_estimators": int(plan.estimators),
                "n_jobs": int(plan.n_jobs),
            },
            "features": features,
            "importance": importance.astype(float).tolist(),
            "importance_norm": importance_norm.astype(float).tolist(),
            "permutation": {
                "values": permutation.astype(float).tolist(),
                "values_norm": permutation_norm.astype(float).tolist(),
                "status": permutation_status,
            },
            "shap": {
                "available": bool(shap_payload.get("available", False)),
                "reason": shap_payload.get("reason", ""),
                "values": shap_payload.get("values", []),
                "values_norm": shap_payload.get("values_norm", []),
                "summary": shap_payload.get("summary", []),
                "similarity": shap_payload.get("similarity", {"available": False, "links": []}),
            },
            "ranking": ranking,
            "settings": {
                "adaptive_cpu": plan.as_dict(),
                "sampling": {
                    "training": "uniform_reservoir_training_partition",
                    "permutation": "held_out_rows",
                    "training_rows": len(train),
                    "evaluation_rows": len(evaluation),
                    "shap": "deterministic_random_subset",
                },
                "local_only": True,
                "future_hooks": {
                    "quantization": "reserved_for_future_local_neural_summaries"
                },
            },
        }

    def _make_cpu_plan(self, rows, features, argms):
        rows = max(0, int(rows))
        features = max(1, int(features))
        available_mb = _available_memory_mb()
        cells = rows * features
        cpu_count = max(1, os.cpu_count() or 1)
        n_jobs = 1

        if cells >= 20_000_000 or features >= 1500 or (available_mb is not None and available_mb < 1024):
            mode = "constrained"
            estimators = 24
            train_rows = 1500
            permutation_rows = 300
            permutation_repeats = 1
            shap_rows = 96
            n_jobs = 1
        elif cells >= 5_000_000 or features >= 750 or (available_mb is not None and available_mb < 2048):
            mode = "balanced"
            estimators = 32
            train_rows = 3000
            permutation_rows = 500
            permutation_repeats = 1
            shap_rows = 128
        else:
            mode = "standard"
            estimators = 64
            train_rows = 8000
            permutation_rows = 1000
            permutation_repeats = 2
            shap_rows = 256

        estimators = _int_arg(argms, "xai_estimators", estimators, minimum=4, maximum=256)
        train_rows = _int_arg(argms, "xai_train_rows", train_rows, minimum=2, maximum=50000)
        permutation_rows = _int_arg(
            argms, "xai_permutation_rows", permutation_rows, minimum=2, maximum=20000
        )
        permutation_repeats = _int_arg(
            argms, "xai_permutation_repeats", permutation_repeats, minimum=1, maximum=10
        )
        shap_rows = _int_arg(argms, "xai_shap_rows", shap_rows, minimum=8, maximum=2000)
        n_jobs = _int_arg(argms, "xai_n_jobs", n_jobs, minimum=1, maximum=max(1, cpu_count))

        if rows > 0:
            train_rows = min(train_rows, rows)
            permutation_rows = min(permutation_rows, train_rows)
            shap_rows = min(shap_rows, train_rows)

        return CPUPlan(
            total_rows=rows,
            total_features=features,
            train_rows=train_rows,
            permutation_rows=permutation_rows,
            permutation_repeats=permutation_repeats,
            shap_rows=shap_rows,
            estimators=estimators,
            available_memory_mb=available_mb,
            n_jobs=n_jobs,
            mode=mode,
        )

    def _read_training_frame(self, csv_path, header, feature_ids, target_id, train_rows):
        use_ids = sorted(set(feature_ids + [target_id]))
        use_columns = [header[index] for index in use_ids]
        frame, _, _ = sample_csv(csv_path, max(2, int(train_rows)), usecols=use_columns,
                                 seed=self.random_state, protect_column=header[target_id])
        return frame

    def _evaluation_split(self, y, task_type):
        indices = np.arange(len(y))
        if len(y) < 8:
            return indices, np.empty(0, dtype=int)
        stratify = None
        if task_type == "classification":
            _, counts = np.unique(y, return_counts=True)
            test_size = max(2, int(np.ceil(len(y) * 0.25)))
            if counts.min() < 2 or len(counts) > min(test_size, len(y) - test_size):
                return indices, np.empty(0, dtype=int)
            stratify = y
        return train_test_split(indices, test_size=0.25, random_state=self.random_state,
                                stratify=stratify)

    def _prepare_arrays(self, frame, header, feature_ids, target_id, impute=True):
        feature_columns = [header[index] for index in feature_ids]
        target_column = header[target_id]

        X = frame.loc[:, feature_columns].apply(pd.to_numeric, errors="coerce")
        y = pd.to_numeric(frame.loc[:, target_column], errors="coerce")

        valid = np.isfinite(y.to_numpy(dtype=float))
        if valid.size and not np.all(valid):
            X = X.loc[valid, :]
            y = y.loc[valid]

        X_values = X.to_numpy(dtype=np.float32, copy=True)
        X_values[~np.isfinite(X_values)] = np.nan
        if impute and not np.isfinite(X_values).all():
            medians = np.nanmedian(X_values, axis=0)
            medians = np.where(np.isfinite(medians), medians, 0.0)
            bad_rows, bad_cols = np.where(~np.isfinite(X_values))
            X_values[bad_rows, bad_cols] = medians[bad_cols]

        y_values = y.to_numpy(dtype=np.float64, copy=True)
        return np.ascontiguousarray(X_values, dtype=np.float32), y_values

    def _infer_task_type(self, y):
        inferred = type_of_target(y)
        if inferred in ("binary", "multiclass"):
            return "classification"
        return "regression"

    def _fit_model(self, X, y, task_type, plan):
        kwargs = {
            "n_estimators": plan.estimators,
            "random_state": self.random_state,
            "n_jobs": plan.n_jobs,
            "max_features": "sqrt",
            "min_samples_leaf": 1,
        }
        if task_type == "classification":
            model = ExtraTreesClassifier(**kwargs)
        else:
            model = ExtraTreesRegressor(**kwargs)
        try:
            model.fit(X, y)
        except PermissionError:
            if plan.n_jobs == 1:
                raise
            plan.n_jobs = 1
            kwargs["n_jobs"] = 1
            model = ExtraTreesClassifier(**kwargs) if task_type == "classification" else ExtraTreesRegressor(**kwargs)
            model.fit(X, y)
        return model

    def _compute_permutation(self, model, X, y, plan):
        if X.shape[0] < 2:
            zeros = np.zeros(X.shape[1], dtype=float)
            return zeros, zeros, "skipped: not enough independent evaluation rows"

        try:
            idx = _sample_indices(self.rng, X.shape[0], plan.permutation_rows)
            result = permutation_importance(
                model,
                X[idx],
                y[idx],
                n_repeats=plan.permutation_repeats,
                random_state=self.random_state,
                n_jobs=1,
            )
            values = _finite_vector(result.importances_mean)
            return values, _normalize_nonnegative(values), "ok"
        except Exception as exc:
            zeros = np.zeros(X.shape[1], dtype=float)
            return zeros, zeros, "skipped: {}".format(str(exc))

    def _compute_shap(self, model, X, feature_ids, columns, plan, argms):
        if not _bool_arg(argms, "xai_enable_shap", True):
            return {
                "available": False,
                "reason": "disabled by xai_enable_shap",
                "values": [],
                "values_norm": [],
                "summary": [],
                "similarity": {"available": False, "links": []},
            }

        try:
            import shap
        except Exception:
            return {
                "available": False,
                "reason": "shap is not installed",
                "values": [],
                "values_norm": [],
                "summary": [],
                "similarity": {"available": False, "links": []},
            }

        try:
            idx = _sample_indices(self.rng, X.shape[0], plan.shap_rows)
            X_shap = X[idx]
            explainer = shap.TreeExplainer(model)
            raw_values = explainer.shap_values(X_shap)
            matrix = _collapse_shap_values(raw_values, X.shape[1])
            values = _finite_vector(np.mean(np.abs(matrix), axis=0))
            values_norm = _normalize_nonnegative(values)
            summary = [
                {
                    "id": int(feature_ids[i]),
                    "name": columns[feature_ids[i]],
                    "mean_abs": float(values[i]),
                    "mean_abs_norm": float(values_norm[i]),
                }
                for i in range(len(feature_ids))
            ]
            return {
                "available": True,
                "reason": "",
                "values": values.astype(float).tolist(),
                "values_norm": values_norm.astype(float).tolist(),
                "summary": summary,
                "similarity": _make_shap_similarity(matrix, feature_ids),
            }
        except Exception as exc:
            return {
                "available": False,
                "reason": "shap failed: {}".format(str(exc)),
                "values": [],
                "values_norm": [],
                "summary": [],
                "similarity": {"available": False, "links": []},
            }


def _collapse_shap_values(raw_values, n_features):
    if isinstance(raw_values, list):
        arrays = [np.asarray(value, dtype=np.float32) for value in raw_values]
        arrays = [value for value in arrays if value.ndim >= 2]
        if not arrays:
            return np.zeros((0, n_features), dtype=np.float32)
        stacked = np.stack([_to_sample_feature_matrix(value, n_features) for value in arrays])
        return np.mean(stacked, axis=0)
    return _to_sample_feature_matrix(np.asarray(raw_values, dtype=np.float32), n_features)


def _to_sample_feature_matrix(values, n_features):
    arr = np.asarray(values, dtype=np.float32)
    if arr.ndim == 3:
        if arr.shape[1] == n_features:
            arr = np.mean(arr, axis=2)
        elif arr.shape[2] == n_features:
            arr = np.mean(arr, axis=0)
        else:
            arr = arr.reshape(arr.shape[0], -1)[:, :n_features]
    elif arr.ndim == 1:
        arr = arr.reshape(1, -1)
    if arr.shape[1] != n_features:
        if arr.shape[0] == n_features:
            arr = arr.T
        else:
            padded = np.zeros((arr.shape[0], n_features), dtype=np.float32)
            width = min(arr.shape[1], n_features)
            padded[:, :width] = arr[:, :width]
            arr = padded
    return np.nan_to_num(arr, copy=False)


def _make_shap_similarity(matrix, feature_ids):
    if matrix.size == 0 or matrix.shape[1] < 2:
        return {"available": False, "links": []}

    profiles = np.asarray(matrix, dtype=np.float32).T
    profiles = profiles - profiles.mean(axis=1, keepdims=True)
    norms = np.linalg.norm(profiles, axis=1)
    usable = norms > 1e-8
    if int(usable.sum()) < 2:
        return {"available": False, "links": []}

    profiles = profiles[usable]
    usable_ids = np.asarray(feature_ids, dtype=int)[usable]
    if profiles.shape[0] > 1000:
        scores = np.mean(np.abs(profiles), axis=1)
        keep = np.argsort(-scores)[:1000]
        profiles = profiles[keep]
        usable_ids = usable_ids[keep]
    norms = np.maximum(np.linalg.norm(profiles, axis=1, keepdims=True), 1e-8)
    profiles = profiles / norms
    sim = profiles @ profiles.T
    links = []
    max_links = min(3000, max(10, len(usable_ids) * 4))
    min_similarity = 0.35
    for i in range(sim.shape[0]):
        row = sim[i]
        candidates = np.argsort(-row)[:12]
        for j in candidates:
            if j <= i:
                continue
            score = float(row[j])
            if score < min_similarity:
                continue
            links.append({
                "source": int(usable_ids[i]),
                "target": int(usable_ids[j]),
                "weight": score,
            })

    links.sort(key=lambda item: item["weight"], reverse=True)
    return {
        "available": bool(links),
        "links": links[:max_links],
    }


def _normalize_nonnegative(values):
    arr = np.asarray(values, dtype=float)
    arr = np.where(np.isfinite(arr), arr, 0.0)
    arr = np.maximum(arr, 0.0)
    mx = float(arr.max()) if arr.size else 0.0
    if mx <= 1e-12:
        return np.zeros_like(arr, dtype=float)
    return arr / mx


def _finite_vector(values):
    arr = np.asarray(values, dtype=float)
    return np.where(np.isfinite(arr), arr, 0.0)


def _sample_indices(rng, n_rows, sample_rows):
    n_rows = int(n_rows)
    sample_rows = min(n_rows, max(1, int(sample_rows)))
    if sample_rows >= n_rows:
        return np.arange(n_rows)
    return np.sort(rng.choice(n_rows, sample_rows, replace=False))


def _count_csv_rows(path):
    count = 0
    last = b""
    with open(path, "rb") as fp:
        while True:
            chunk = fp.read(1024 * 1024)
            if not chunk:
                break
            count += chunk.count(b"\n")
            last = chunk[-1:]
    if last and last not in (b"\n", b"\r"):
        count += 1
    return max(0, count - 1)


def _available_memory_mb():
    try:
        import psutil
        return round(float(psutil.virtual_memory().available) / (1024.0 * 1024.0), 2)
    except Exception:
        return None


def _int_arg(argms, name, default, minimum=None, maximum=None):
    try:
        value = int(argms.get(name, default))
    except (TypeError, ValueError):
        value = int(default)
    if minimum is not None:
        value = max(int(minimum), value)
    if maximum is not None:
        value = min(int(maximum), value)
    return value


def _target_id_arg(value, fallback):
    if value is None:
        return int(fallback)
    try:
        if isinstance(value, float) and np.isnan(value):
            return int(fallback)
        return int(value)
    except (TypeError, ValueError):
        return int(fallback)


def _bool_arg(argms, name, default):
    value = argms.get(name, default)
    if isinstance(value, str):
        return value.strip().lower() not in ("0", "false", "no", "off")
    return bool(value)


def _is_int_like(value):
    try:
        int(value)
        return True
    except (TypeError, ValueError):
        return False


class ContrastiveSubspaceExplainer:
    """
    Closed-Loop Contrastive & Counterfactual Subspace Explainer (CCSE) for GFF+.

    Given a brushed subset of instances (Group A) and either a second brushed subset
    (Group B) or the complement of the dataset (Rest), computes:
      1. Local Contrastive Effect Sizes (Delta_f): Standardized mean difference
         (signed Cohen's d) and Welch t-statistic across all features, normalized to [-1, 1].
      2. Counterfactual Subspace Gain (G_f): Ranks unselected features by how strongly
         adding f either (a) increases separation between Group A and Group B, or
         (b) resolves target-class impurity within Group A while maintaining low
         redundancy (orthogonality) against the currently selected feature subset.
    """

    @staticmethod
    def benjamini_hochberg(p_values):
        """
        Benjamini-Hochberg (BH) step-up False Discovery Rate (FDR) adjustment.
        Computes adjusted q-values in [0, 1] with monotonicity enforced.
        """
        p = np.asarray(p_values, dtype=np.float64)
        m = len(p)
        if m == 0:
            return np.array([], dtype=np.float64)
        if m == 1:
            return np.clip(p, 0.0, 1.0)
        sort_idx = np.argsort(p)
        p_sorted = p[sort_idx]
        ranks = np.arange(1, m + 1, dtype=np.float64)
        q_sorted = p_sorted * (float(m) / ranks)
        # Enforce backwards monotonicity: q_(i) <= q_(i+1)
        q_sorted = np.minimum.accumulate(q_sorted[::-1])[::-1]
        q_sorted = np.clip(q_sorted, 0.0, 1.0)
        q_values = np.empty_like(q_sorted)
        q_values[sort_idx] = q_sorted
        return q_values

    @staticmethod
    def welch_t_test(X_a, X_b):
        """
        Welch's two-sample unequal variances t-test across all columns.
        Returns:
            t_stat: 1D array of Welch t-statistics
            p_val: 1D array of two-tailed p-values
            welch_df: 1D array of Welch-Satterthwaite degrees of freedom
        Handles edge cases:
            - n_a <= 1 or n_b <= 1 -> t=0.0, p=1.0, df=max(1.0, n_a + n_b - 2)
            - zero variance (s_a^2 = 0 and s_b^2 = 0) -> t=0.0, p=1.0
            - constant features -> t=0.0, p=1.0
            - nu_f < 1.0 -> bounded to nu_f >= 1.0
        """
        from scipy import stats

        X_a = np.asarray(X_a, dtype=np.float64)
        X_b = np.asarray(X_b, dtype=np.float64)
        if X_a.ndim == 1:
            X_a = X_a[:, np.newaxis]
        if X_b.ndim == 1:
            X_b = X_b[:, np.newaxis]

        n_a, m_features = X_a.shape
        n_b = X_b.shape[0]

        t_stat = np.zeros(m_features, dtype=np.float64)
        p_val = np.ones(m_features, dtype=np.float64)
        welch_df = np.full(m_features, max(1.0, float(n_a + n_b - 2)), dtype=np.float64)

        if n_a <= 1 or n_b <= 1 or m_features == 0:
            return t_stat, p_val, welch_df

        mean_a = np.mean(X_a, axis=0)
        mean_b = np.mean(X_b, axis=0)
        var_a = np.var(X_a, axis=0, ddof=1)
        var_b = np.var(X_b, axis=0, ddof=1)

        s_a = var_a / float(n_a)
        s_b = var_b / float(n_b)
        denom_se = np.sqrt(s_a + s_b)

        valid_mask = denom_se > 1e-12
        if np.any(valid_mask):
            t_stat[valid_mask] = (mean_a[valid_mask] - mean_b[valid_mask]) / denom_se[valid_mask]

            num_df = (s_a[valid_mask] + s_b[valid_mask]) ** 2
            denom_df = ((s_a[valid_mask] ** 2) / (n_a - 1)) + ((s_b[valid_mask] ** 2) / (n_b - 1))

            safe_df_mask = denom_df > 1e-15
            cur_dfs = np.full(int(np.sum(valid_mask)), max(1.0, float(n_a + n_b - 2)), dtype=np.float64)
            cur_dfs[safe_df_mask] = np.maximum(1.0, num_df[safe_df_mask] / denom_df[safe_df_mask])
            welch_df[valid_mask] = cur_dfs

            raw_p = 2.0 * stats.t.sf(np.abs(t_stat[valid_mask]), df=welch_df[valid_mask])
            raw_p = np.where(np.isfinite(raw_p), raw_p, 1.0)
            p_val[valid_mask] = np.clip(raw_p, 0.0, 1.0)

        return t_stat, p_val, welch_df

    def execute(self, data_path, argms):
        from time import perf_counter
        started = perf_counter()
        dataset_id = str(argms.get("file", "")).strip()
        if not dataset_id:
            raise ValueError("Dataset file id is required")

        filefepath = os.path.join(str(data_path), dataset_id)
        csv_path = os.path.join(filefepath, "transform.csv")
        if not os.path.isfile(csv_path):
            raise FileNotFoundError("Dataset file not found: {}".format(csv_path))

        from vx.com.px.dataset.dataio_pure import DataMatrix
        from vx.gff.Ingestion import source_ids

        XDF = DataMatrix(csv_path, max_rows=5000, dtype=np.float64)
        colsnames = XDF.columns_index()
        trueids = XDF.trueids()
        local_ids = XDF._row_ids
        orig_row_ids = source_ids(filefepath, local_ids)

        target_orig = _target_id_arg(argms.get("target"), len(trueids) - 1)
        target_local = trueids[target_orig] if 0 <= target_orig < len(trueids) else -1

        selected_set = set()
        for idx in argms.get("featureselected", []):
            try:
                val = int(idx)
            except (TypeError, ValueError):
                continue
            if val != target_orig:
                selected_set.add(val)

        group_a_raw = argms.get("group_a_ids", argms.get("selected_instances", []))
        group_b_raw = argms.get("group_b_ids", [])
        group_a_set = {int(x) for x in group_a_raw if _is_int_like(x)}
        group_b_set = {int(x) for x in group_b_raw if _is_int_like(x)} - group_a_set

        mask_a = np.isin(orig_row_ids, list(group_a_set)) if group_a_set else np.zeros(len(orig_row_ids), dtype=bool)
        if group_b_set:
            mask_b = np.isin(orig_row_ids, list(group_b_set))
            comparison_mode = "a_vs_b"
        else:
            mask_b = ~mask_a
            comparison_mode = "a_vs_rest"

        n_a = int(mask_a.sum())
        n_b = int(mask_b.sum())
        if n_a == 0 or n_b == 0:
            return {
                "status": "empty",
                "reason": "Select at least one instance in the projection to compute contrastive & counterfactual attributions.",
                "comparison_mode": comparison_mode,
                "group_a_count": n_a,
                "group_b_count": n_b,
                "features": [],
                "contrastive_features": [],
                "by_feature_id": {},
                "top_contrastive": [],
                "top_counterfactual": [],
                "counterfactual_candidates": [],
                "summary_text": "Lasso a cluster of instances in the 2D projection to inspect local feature drivers and counterfactual subspace recommendations.",
            }

        # Map original feature IDs to local columns
        feature_entries = []
        for orig_id, local_id in enumerate(trueids):
            if local_id >= 0 and orig_id != target_orig:
                feature_entries.append((orig_id, local_id, str(colsnames[local_id])))

        if not feature_entries:
            return {
                "status": "empty",
                "reason": "No non-target features available.",
                "comparison_mode": comparison_mode,
                "group_a_count": n_a,
                "group_b_count": n_b,
                "features": [],
                "contrastive_features": [],
                "by_feature_id": {},
                "top_contrastive": [],
                "top_counterfactual": [],
                "counterfactual_candidates": [],
                "summary_text": "",
            }

        orig_fids = [e[0] for e in feature_entries]
        local_fids = [e[1] for e in feature_entries]
        fnames = [e[2] for e in feature_entries]

        # If no explicit subset was checked, consider all non-target features selected unless passed
        has_explicit_selection = bool(selected_set) and len(selected_set) < len(orig_fids)

        X_all = np.nan_to_num(XDF.selectcolumns_index(local_fids)._data, copy=True)
        y_all = (
            np.nan_to_num(XDF.getcolumn_array(target_local, copy=True).astype(np.float64), copy=False)
            if target_local >= 0
            else np.zeros(X_all.shape[0], dtype=np.float64)
        )

        X_a = X_all[mask_a]
        X_b = X_all[mask_b]
        y_a = y_all[mask_a]

        mean_a = np.mean(X_a, axis=0)
        mean_b = np.mean(X_b, axis=0)
        var_a = np.var(X_a, axis=0, ddof=1) if n_a > 1 else np.zeros(X_all.shape[1])
        var_b = np.var(X_b, axis=0, ddof=1) if n_b > 1 else np.zeros(X_all.shape[1])

        denom_pool = np.sqrt(np.maximum(((max(1, n_a - 1) * var_a) + (max(1, n_b - 1) * var_b)) / max(1, n_a + n_b - 2), 1e-12))
        global_std = np.maximum(np.std(X_all, axis=0), 1e-12)
        scale = np.where(denom_pool > 1e-9, denom_pool, global_std)

        # Signed Cohen's d effect size: positive => higher in Group A, negative => lower in Group A (higher in B/Rest)
        cohens_d = (mean_a - mean_b) / scale
        cohens_d = np.where(np.isfinite(cohens_d), cohens_d, 0.0)
        abs_d = np.abs(cohens_d)
        max_abs_d = float(np.max(abs_d)) if abs_d.size else 0.0
        contrast_norm = (cohens_d / max_abs_d) if max_abs_d > 1e-12 else np.zeros_like(cohens_d)

        # Welch's unequal variances t-test and Benjamini-Hochberg FDR correction
        t_stat, p_val, welch_df = self.welch_t_test(X_a, X_b)
        fdr_q_val = self.benjamini_hochberg(p_val)

        # Target-class impurity within Group A (for classification targets)
        inferred_task = type_of_target(y_all)
        is_classification = inferred_task in ("binary", "multiclass")
        group_a_purity = 1.0
        within_a_sep = np.zeros(X_all.shape[1], dtype=np.float64)
        if is_classification and n_a >= 2:
            classes_a, counts_a = np.unique(y_a, return_counts=True)
            group_a_purity = float(np.max(counts_a)) / float(n_a)
            if len(classes_a) >= 2:
                # Measure how strongly each feature separates the top two target classes mixed inside Group A
                top_two = classes_a[np.argsort(-counts_a)[:2]]
                c1_mask = y_a == top_two[0]
                c2_mask = y_a == top_two[1]
                if c1_mask.sum() >= 1 and c2_mask.sum() >= 1:
                    m1 = np.mean(X_a[c1_mask], axis=0)
                    m2 = np.mean(X_a[c2_mask], axis=0)
                    within_a_sep = np.abs(m1 - m2) / global_std
                    within_a_sep = np.where(np.isfinite(within_a_sep), within_a_sep, 0.0)

        # Compute redundancy (maximum absolute correlation) of each feature against selected features
        redundancy = np.zeros(X_all.shape[1], dtype=np.float64)
        if has_explicit_selection:
            sel_cols = [idx for idx, fid in enumerate(orig_fids) if fid in selected_set]
            if sel_cols:
                X_centered = X_all - np.mean(X_all, axis=0, keepdims=True)
                norms = np.linalg.norm(X_centered, axis=0, keepdims=True)
                X_unit = np.divide(X_centered, np.maximum(norms, 1e-12))
                corr_mat = np.abs(X_unit.T @ X_unit[:, sel_cols])
                redundancy = np.clip(np.max(corr_mat, axis=1), 0.0, 1.0)

        # Counterfactual Gain (G_f):
        # Combines between-group discriminative power (|d|) and within-group class-splitting power
        # weighted by novelty (1 - 0.5 * redundancy) so recommended features add orthogonal signal.
        raw_disc = 0.65 * _normalize_nonnegative(abs_d) + 0.35 * _normalize_nonnegative(within_a_sep)
        novelty_factor = 1.0 - 0.5 * redundancy
        cf_scores = raw_disc * novelty_factor
        # For unselected features, normalize counterfactual gain to [0, 1]
        if has_explicit_selection:
            unsel_mask = np.array([fid not in selected_set for fid in orig_fids], dtype=bool)
            unsel_max = float(np.max(cf_scores[unsel_mask])) if np.any(unsel_mask) else 0.0
            cf_norm = np.where(unsel_mask, cf_scores / max(unsel_max, 1e-12), 0.0)
        else:
            cf_norm = _normalize_nonnegative(cf_scores)

        features_out = []
        by_feature_id = {}
        for i, fid in enumerate(orig_fids):
            is_sel = (fid in selected_set) if has_explicit_selection else True
            q_val = float(fdr_q_val[i])
            item = {
                "id": int(fid),
                "feid": int(fid),
                "name": fnames[i],
                "is_selected": bool(is_sel),
                "mean_a": round(float(mean_a[i]), 4),
                "mean_b": round(float(mean_b[i]), 4),
                "mean_group_a": round(float(mean_a[i]), 4),
                "mean_group_b": round(float(mean_b[i]), 4),
                "std_group_a": round(float(np.sqrt(var_a[i])), 4),
                "std_group_b": round(float(np.sqrt(var_b[i])), 4),
                "effect_size": round(float(cohens_d[i]), 4),
                "cohens_d": round(float(cohens_d[i]), 4),
                "abs_effect": round(float(abs_d[i]), 4),
                "contrast_norm": round(float(contrast_norm[i]), 4),
                "delta_normalized": round(float(contrast_norm[i]), 4),
                "t_statistic": round(float(t_stat[i]), 4),
                "p_value": float(p_val[i]),
                "welch_df": round(float(welch_df[i]), 2),
                "fdr_q_value": q_val,
                "is_significant": bool(q_val < 0.05),
                "within_group_sep": round(float(within_a_sep[i]), 4),
                "redundancy": round(float(redundancy[i]), 4),
                "counterfactual_gain": round(float(cf_norm[i]), 4),
            }
            features_out.append(item)
            by_feature_id[str(fid)] = item

        # Rank top contrastive drivers (preferring currently active features when a subset is selected)
        active_Pool = [f for f in features_out if f["is_selected"]] if has_explicit_selection else list(features_out)
        top_contrastive = sorted(active_Pool, key=lambda x: x["abs_effect"], reverse=True)[:8]

        # Rank top counterfactual unselected features (or top under-utilized features if all are selected)
        unsel_Pool = [f for f in features_out if not f["is_selected"]]
        if unsel_Pool:
            top_counterfactual = sorted(unsel_Pool, key=lambda x: x["counterfactual_gain"], reverse=True)[:6]
        else:
            top_counterfactual = sorted(features_out, key=lambda x: x["counterfactual_gain"], reverse=True)[:5]

        # Mark top 3 counterfactual candidates on by_feature_id for the force-graph dashed halo
        top_cf_ids = {f["id"] for f in top_counterfactual[:3] if not f["is_selected"] or not has_explicit_selection}
        for f in features_out:
            f["is_top_counterfactual"] = f["id"] in top_cf_ids

        comp_label = "Group B ({} pts)".format(n_b) if comparison_mode == "a_vs_b" else "Rest ({} pts)".format(n_b)
        summary_parts = [
            "Comparing Group A ({} pts, purity {:.0%}) vs. {}.".format(n_a, group_a_purity, comp_label)
        ]
        if top_contrastive:
            lead = top_contrastive[0]
            direction = "higher" if lead["effect_size"] >= 0 else "lower"
            sig_label = " (significant, FDR q={:.2e})".format(lead["fdr_q_value"]) if lead["is_significant"] else ""
            summary_parts.append(
                "Primary driver: {} ({} in Group A, d={:+.2f}{}).".format(
                    lead["name"], direction, lead["effect_size"], sig_label
                )
            )
        if top_counterfactual and has_explicit_selection:
            best_cf = top_counterfactual[0]
            summary_parts.append(
                "Top counterfactual addition: {} (gain {:.2f}, redundancy {:.0%}).".format(
                    best_cf["name"], best_cf["counterfactual_gain"], best_cf["redundancy"]
                )
            )

        return {
            "status": "ok",
            "comparison_mode": comparison_mode,
            "has_explicit_selection": has_explicit_selection,
            "group_a_count": n_a,
            "group_b_count": n_b,
            "group_a_purity": round(group_a_purity, 4),
            "elapsed_ms": round((perf_counter() - started) * 1000.0, 2),
            "features": features_out,
            "contrastive_features": features_out,
            "by_feature_id": by_feature_id,
            "top_contrastive": top_contrastive,
            "top_counterfactual": top_counterfactual,
            "counterfactual_candidates": top_counterfactual,
            "summary_text": " ".join(summary_parts),
        }
