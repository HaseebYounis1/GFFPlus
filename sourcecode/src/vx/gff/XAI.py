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
        target_id = int(argms.get("target", -1))
        csv_path = os.path.join(data_path, dataset_id, "transform.csv")
        if not os.path.exists(csv_path):
            raise FileNotFoundError("transform.csv was not found for dataset {}".format(dataset_id))

        header = pd.read_csv(csv_path, nrows=0, encoding="utf-8-sig").columns
        columns = [str(col).strip() for col in header]
        if feature_names and len(feature_names) == len(columns):
            columns = [str(col).strip() for col in feature_names]

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
        X, y = self._prepare_arrays(frame, header, feature_ids, target_id)

        if X.shape[0] < 2:
            raise ValueError("XAI needs at least two valid data rows after loading.")

        task_type = self._infer_task_type(y)
        if task_type == "classification" and np.unique(y).size < 2:
            raise ValueError("Classification XAI needs at least two target classes.")

        model = self._fit_model(X, y, task_type, plan)
        importance = _finite_vector(getattr(model, "feature_importances_", np.zeros(X.shape[1])))
        importance_norm = _normalize_nonnegative(importance)

        permutation, permutation_norm, permutation_status = self._compute_permutation(
            model, X, y, plan
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
                    "training": "first_rows",
                    "permutation": "deterministic_random_subset",
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
        return pd.read_csv(
            csv_path,
            delimiter=",",
            encoding="utf-8-sig",
            usecols=use_columns,
            nrows=max(2, int(train_rows)),
        )

    def _prepare_arrays(self, frame, header, feature_ids, target_id):
        feature_columns = [header[index] for index in feature_ids]
        target_column = header[target_id]

        X = frame.loc[:, feature_columns].apply(pd.to_numeric, errors="coerce")
        y = pd.to_numeric(frame.loc[:, target_column], errors="coerce")

        valid = y.notna().to_numpy()
        if valid.size and not np.all(valid):
            X = X.loc[valid, :]
            y = y.loc[valid]

        X_values = X.to_numpy(dtype=np.float32, copy=True)
        if np.isnan(X_values).any():
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
            return zeros, zeros, "skipped: not enough rows"

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
