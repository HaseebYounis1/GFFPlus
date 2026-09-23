"""Memory-bounded facility-location shortlisting of row or module vectors."""
import operator

import numpy as np
from scipy.spatial.distance import cdist


def shortlist(X, size, *, random_state=7, max_reference=512,
              batch_size=128, epsilon=0.1, metric="euclidean"):
    """Return unique original indices in greedy selection order.

    Maximise sum_r max_{j in S} similarity(r, j), with similarity
    1/(1+Euclidean distance), or clipped cosine similarity. All items remain
    candidates; at most max_reference uniformly sampled items define coverage.
    Stochastic greedy evaluates ceil(n/size * log(1/epsilon)) candidates per
    round. epsilon=0 evaluates every remaining candidate (exact greedy for
    the reference objective). No n-by-n similarity matrix is constructed.

    Rows can be instances, feature profiles (pass X.T), or module embeddings.
    Scale numeric features beforehand if their units should have equal weight.
    """
    data = np.asarray(X, dtype=np.float64)
    if data.ndim != 2 or not np.isfinite(data).all():
        raise ValueError("X must be a finite numeric 2-D matrix")
    size = operator.index(size)
    max_reference = operator.index(max_reference)
    batch_size = operator.index(batch_size)
    n = len(data)
    if not 0 <= size <= n:
        raise ValueError("size must be between zero and the number of items")
    if max_reference < 1 or batch_size < 1 or not 0 <= epsilon < 1:
        raise ValueError("positive reference/batch limits and 0 <= epsilon < 1 required")
    if metric not in ("euclidean", "cosine"):
        raise ValueError("metric must be euclidean or cosine")
    if size == 0:
        return []
    if size == n:
        return list(range(n))
    rng = np.random.default_rng(random_state)
    refs = data if n <= max_reference else data[
        np.sort(rng.choice(n, max_reference, replace=False))]
    coverage = np.zeros(len(refs))
    available = np.ones(n, dtype=bool)
    selected = []
    candidate_count = n if epsilon == 0 else max(1, int(np.ceil(n / size * np.log(1 / epsilon))))
    for _ in range(size):
        candidates = np.flatnonzero(available)
        if len(candidates) > candidate_count:
            candidates = np.sort(rng.choice(candidates, candidate_count, replace=False))
        best_gain, best_id, best_cover = -1.0, None, None
        for start in range(0, len(candidates), batch_size):
            ids = candidates[start:start + batch_size]
            if metric == "euclidean":
                similarity = 1.0 / (1.0 + cdist(data[ids], refs))
            else:
                a, b = data[ids], refs
                denom = np.linalg.norm(a, axis=1)[:, None] * np.linalg.norm(b, axis=1)
                similarity = np.divide(a @ b.T, denom, out=np.zeros_like(denom), where=denom > 0)
                similarity = np.clip(similarity, 0, 1)
            covered = np.maximum(similarity, coverage)
            gains = (covered - coverage).sum(axis=1)
            local = int(np.argmax(gains))
            if gains[local] > best_gain:
                best_gain, best_id = float(gains[local]), int(ids[local])
                best_cover = covered[local].copy()
        selected.append(best_id)
        available[best_id] = False
        coverage = best_cover
    return selected
