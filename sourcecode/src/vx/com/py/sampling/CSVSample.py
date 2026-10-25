"""Deterministic CSV samples spanning the entire file, with bounded row storage."""
import numpy as np
import pandas as pd


def sample_csv(path, limit, *, usecols=None, dtype=None, seed=7, protect_column=None):
    if limit < 1:
        raise ValueError("Sample limit must be positive")
    header = pd.read_csv(path, nrows=0, encoding="utf-8-sig")
    width = max(1, len(header.columns))
    chunk_size = max(1, min(4096, 262144 // width))
    rng = np.random.default_rng(seed)
    kept, keys, ids = None, np.empty(0), np.empty(0, dtype=np.int64)
    total, protected, protect = 0, {}, protect_column is not None
    with pd.read_csv(path, chunksize=chunk_size, usecols=usecols, dtype=dtype,
                     encoding="utf-8-sig") as reader:
        for chunk in reader:
            chunk_ids = np.arange(total, total + len(chunk))
            total += len(chunk)
            if protect:
                for value, group in chunk.groupby(protect_column, dropna=False, sort=False):
                    key = str(value)
                    if key not in protected:
                        # Preserve one example of each low-cardinality class,
                        # including a class that occurs only near the file end.
                        pos = chunk.index.get_indexer([group.index[0]])[0]
                        protected[key] = (int(chunk_ids[pos]), group.iloc[[0]].copy())
                    if len(protected) > min(100, limit):
                        protected.clear()
                        protect = False
                        break
            new_keys = rng.random(len(chunk))
            kept = chunk.copy() if kept is None else pd.concat([kept, chunk], ignore_index=True)
            keys = np.concatenate([keys, new_keys])
            ids = np.concatenate([ids, chunk_ids])
            if len(keys) > limit:
                keep = np.argpartition(keys, limit - 1)[:limit]
                kept, keys, ids = kept.iloc[keep].reset_index(drop=True), keys[keep], ids[keep]
    if kept is None:
        kept = header if usecols is None else pd.read_csv(path, nrows=0, usecols=usecols)
    # Replace reservoir rows, rather than exceeding the requested memory budget.
    protected_ids = {item[0] for item in protected.values()}
    for source_id, row in protected.values():
        if source_id not in ids:
            replace = next(i for i, value in enumerate(ids) if value not in protected_ids)
            kept.iloc[replace] = row.iloc[0]
            ids[replace] = source_id
    order = np.argsort(ids)
    return kept.iloc[order].reset_index(drop=True), ids[order], total


def read_rows(path, row_ids, *, usecols=None):
    """Read only requested records, preserving their requested order."""
    wanted = {int(i) for i in row_ids}
    found = {}
    if wanted:
        with pd.read_csv(path, chunksize=4096, usecols=usecols, dtype=str,
                         encoding="utf-8-sig") as reader:
            offset = 0
            for chunk in reader:
                for index in wanted.intersection(range(offset, offset + len(chunk))):
                    found[index] = chunk.iloc[index - offset].tolist()
                offset += len(chunk)
                if len(found) == len(wanted):
                    break
    if len(found) != len(wanted):
        raise ValueError("Saved source row IDs do not match the original CSV")
    return [found[int(index)] for index in row_ids]
