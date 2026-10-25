"""Keep source CSVs on disk and build a representative working dataset."""
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from vx.com.py.sampling.CSVSample import sample_csv
from vx.com.py.sampling.Submodular import shortlist


def ingest_csv(directory, budget=None):
    directory = Path(directory)
    source = directory / "original.csv"
    columns = pd.read_csv(source, nrows=0, encoding="utf-8-sig").columns
    if len(columns) < 2:
        raise ValueError("The CSV needs at least one feature and a target column")
    # Budget for raw strings, numeric copies and the candidate reservoir.
    automatic = max(128, min(3000, 32 * 1024**2 // (len(columns) * 128)))
    budget = automatic if budget is None else int(budget)
    if not 1 <= budget <= automatic:
        raise ValueError("Row budget exceeds the automatic memory limit")
    frame, ids, total = sample_csv(source, budget * 2, dtype=str,
                                   protect_column=columns[-1])
    if frame.empty:
        raise ValueError("The CSV contains no data rows")
    encoded = {}
    categorical = []
    for column in columns:
        numeric = pd.to_numeric(frame[column], errors="coerce")
        if (numeric.notna() | frame[column].isna()).all():
            numeric = numeric.replace([np.inf, -np.inf], np.nan)
            encoded[column] = numeric.fillna(numeric.median() if numeric.notna().any() else 0)
        else:
            categorical.append(str(column))
            encoded[column] = pd.Categorical(frame[column].fillna("(missing)")).codes
    encoded = pd.DataFrame(encoded, index=frame.index)
    size = min(budget, len(frame))
    vectors = encoded.iloc[:, :-1].to_numpy(dtype=float)
    scale = vectors.std(axis=0)
    vectors = (vectors - vectors.mean(axis=0)) / np.where(scale > 0, scale, 1)
    chosen = shortlist(vectors, size, max_reference=128)
    groups = frame.iloc[:, -1].fillna("(missing)")
    protected = []
    if groups.nunique() <= min(100, size):
        protected = groups.drop_duplicates().index.tolist()
        # Keep coverage choices where possible while retaining every known class.
        chosen = list(dict.fromkeys(protected + chosen))[:size]
    chosen = sorted(chosen, key=lambda i: ids[i])
    frame.iloc[chosen].to_csv(directory / "working.csv", index=False)
    encoded.iloc[chosen].to_csv(directory / "transform.csv", index=False)
    shutil.copyfile(directory / "transform.csv", directory / "sample.csv")
    selected_ids = ids[chosen].astype(int).tolist()
    (directory / "row_ids.json").write_text(json.dumps(selected_ids), encoding="utf-8")
    metadata = {"method": "reservoir_submodular", "original_rows": total,
                "selected_rows": len(chosen), "candidate_rows": len(frame),
                "budget": budget, "seed": 7, "categorical_columns": categorical,
                "protected_column": str(columns[-1]) if protected else None,
                "protected_classes": len(protected)}
    (directory / "sampling.json").write_text(json.dumps(metadata), encoding="utf-8")
    return metadata


def source_ids(directory, local_ids):
    path = Path(directory) / "row_ids.json"
    if not path.exists():
        return np.asarray(local_ids, dtype=np.int64)
    mapping = np.asarray(json.loads(path.read_text(encoding="utf-8")), dtype=np.int64)
    return mapping[np.asarray(local_ids, dtype=int)]


def sampling_metadata(directory):
    path = Path(directory) / "sampling.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
