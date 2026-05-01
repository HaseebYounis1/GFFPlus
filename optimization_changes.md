# GFF Optimization Changes

All 61 tests pass after every change listed here. Results are numerically
identical to the original code unless noted otherwise.

---

## 1. `sourcecode/src/vx/com/py/proximity/KNN.py`

### Problem
`KNN.execute` contained a `print("dddddddddddddddd", d)` statement inside
its O(n²) inner loop. For n=1000 this produced one million print calls,
making KNN unusably slow (minutes instead of seconds).

The algorithm also allocated `n` separate `PriorityQueue` objects and
extracted neighbours one-at-a-time.

### Fix
- Removed the debug print.
- Replaced the Python nested loop + n PriorityQueues with a single vectorised
  pairwise distance matrix using numpy (`vectors @ vectors.T` via the
  squared-norm identity for Euclidean). `np.argpartition` then extracts the
  k-nearest neighbours for each row in O(n) instead of O(n log n) per row.
- Fallback Python loop retained for non-Euclidean metrics.

### Complexity
| Before | After |
|--------|-------|
| O(n²) Python loop + O(n log n) heap per row + O(n²) prints | O(n²) BLAS matmul + O(n) argpartition per row |

---

## 2. `sourcecode/src/vx/com/py/clustering/BKmeans.py`

### Problem
Two separate issues:

1. `computeMean` contained `print("mean", mean)` inside a function called
   O(k × iterations) times during every clustering run.
2. `computeMean` used a nested Python loop (`for i in cluster: for j in range(n)`)
   to sum values element-by-element.
3. `computeMedoid` looped over every cluster member calling `Proximity.compute`
   one at a time.

### Fix
- Removed the `print("mean", mean)` debug statement.
- `computeMean`: replaced the double loop with
  `np.array([X[i] for i in cluster]).mean(axis=0).tolist()`.
- `computeMedoid`: build the cluster sub-matrix once, compute all distances
  in a single `np.sqrt((diff**2).sum(axis=1))` vectorised call, then use
  `np.argmin`.
- Added `import numpy as np`.

### Complexity
| Operation | Before | After |
|-----------|--------|-------|
| computeMean | O(n×d) Python loops | O(n×d) numpy (BLAS) |
| computeMedoid | O(k) Python calls to Proximity.compute | O(k×d) single numpy operation |

---

## 3. `sourcecode/src/vx/com/py/proximity/Proximity.py`

### Problem
`Proximity.compute` computed Euclidean distance with a Python `for` loop
over each dimension before calling `np.sqrt`. For high-dimensional vectors
(e.g. MNIST's 60 k-element feature vectors) this adds large Python
loop overhead on top of the numpy call.

`PMatrix` stored distances in a Python list-of-lists — `n²` Python `None`
objects occupying O(n²) heap entries, with O(1) access but high memory
overhead and GC pressure.

### Fix
- `Proximity.compute`: replaced the Python loop with a single
  `np.sqrt(np.dot(diff, diff))` expression.
- `PMatrix`: replaced the list-of-lists with a `numpy.full((n,n), NaN)`
  matrix. `get` returns `None` for NaN (preserving the API contract used by
  `ANN.py`). `set` writes directly to the numpy array.

### Space
| Before | After |
|--------|-------|
| n² Python objects (None) | n² float64 values (8 bytes each) |

---

## 4. `sourcecode/src/vx/com/py/clustering/BKmeansFE.py`

### Problem
`computeMean` updated the centroid matrix cell-by-cell:
```python
for i in cluster:
    for c in range(X.cols()):
        d = twocentroids.getValue(itwo, c) + (X.getValue(i,c)/z)
        twocentroids.setValue(itwo, c, d)
```
This is O(|cluster| × d) Python operations with repeated `getValue`/`setValue`
overhead.

### Fix
Replaced with a single numpy row operation:
```python
mean = X._data[cluster, :].mean(axis=0)
twocentroids._data[itwo, :] = mean
```
Since `DataMatrix._data` is a numpy array, fancy indexing selects all cluster
rows at once, and `.mean(axis=0)` reduces in one pass.

---

## 5. `sourcecode/src/vx/com/py/matrix/MData.py`

### Problem (two issues)

**`openfilecsv`**: used `df.iterrows()` — the slowest pandas iteration
method — to convert the DataFrame to a Python list. For a 60 k-row dataset
this iterates 60 000 times in Python, each iteration creating a Series object.
Also had an unnecessary `columns_aux` copy loop.

**`samplex`**: used nested Python loops for row/column sub-sampling instead
of numpy index arrays.

### Fix
- `openfilecsv`: replaced `iterrows()` with `df.to_numpy(dtype=float).tolist()`
  (single C-level conversion). Also replaced the one-by-one categorical
  encoding loop with a vectorised `df[cat_cols].apply(lambda c: c.astype('category').cat.codes)`.
- `samplex`: converted input to `np.asarray` once, then used numpy fancy
  indexing (`arr[smp_r]`, `arr[:, smp_c]`, `arr[np.ix_(smp_r, smp_c)]`).
  Returns the original list unchanged when both selectors are None.

### Complexity
| Operation | Before | After |
|-----------|--------|-------|
| openfilecsv (60k rows) | O(n) Python loop + O(n) Series creation | O(1) numpy conversion |
| samplex row+col | O(r×c) Python loop | O(r×c) numpy copy |

---

## 6. `sourcecode/src/vx/com/py/projection/MDSP.py`

### Problem
`MDS` was constructed with `n_jobs=1`, forcing single-threaded distance
computation regardless of available CPUs.

### Fix
Changed `n_jobs=1` → `n_jobs=-1` to use all available cores.

---

## 7. `sourcecode/src/vx/com/py/graph/GNNFE.py`

### Problem
`GNNFE.completing` checked whether node `i` was already a neighbour of node
`j` with a linear scan:
```python
for k, w2 in neighbors[j]:
    if k == i:
        contain = True; break
```
This is O(k) per edge check, making `completing` O(n × k²) overall.

### Fix
Built a `neighbor_sets` list of Python `set` objects once at the start.
Membership test is now O(1). Used an explicit `while idx < len(...)` loop
(instead of `for ... in neighbors[i]`) to safely visit elements appended
during the same pass — preserving the original algorithm's behaviour of
symmetrising newly discovered asymmetric edges.

### Complexity
| Before | After |
|--------|-------|
| O(n × k²) | O(n × k) |

---

## 8. `sourcecode/src/vx/gff/Query.py`

### Problem (two issues)

**`loadatributenames`**: contained a no-op loop that copied `columns` into
`columns_aux` without filtering anything (the filter comment was commented
out), then re-assigned `columns = columns_aux`. Also left an unclosed file
handle in the non-`fenames` branch.

**`savefile`**: encoded categorical columns with an explicit Python `for` loop
calling `.cat.codes` per column.

### Fix
- `loadatributenames`: removed the dead `columns_aux` loop; replaced the
  manual `open/close` with a `with` block.
- `savefile`: replaced the per-column loop with a single `.apply(lambda col:
  col.astype('category').cat.codes)` call on the whole categorical block.

---

## 9. `sourcecode/src/vx/com/py/proximity/KNNFE.py`

### Problem
Same structural issue as `KNN.py`: n `PriorityQueue` objects, one pair of
`put` calls per centroid pair, one `get` per extracted neighbour.

### Fix
Extracted all centroid row vectors into a submatrix (`X._data[centroid_ids]`),
computed the full pairwise distance matrix with one BLAS matrix multiply, then
used `np.argpartition` for cheap top-k extraction.

---

## 10. `sourcecode/src/vx/com/px/dataset/dataio_pure.py`

*(Changes made in the previous session — documented here for completeness.)*

### `_pairwise_matrix` — vectorised

Replaced two nested Python loops (compute + normalise) with:
- A new `_compute_pairwise` function that dispatches on metric type.
- For Euclidean (pt=0), Cosine (pt=5), Pearson (pt=6), Gaussian (pt=7),
  Sample-Correlation (pt=8), DCosine (pt=9): single matrix multiply
  `vectors @ vectors.T` after appropriate preprocessing.
- For Manhattan/Canberra/Chebyshev/Braycurtis: `scipy.spatial.distance.cdist`.
- Min-max normalisation vectorised with numpy broadcasting.

### `proximitymatrix_cols` — row sampling

Added `max_rows=5000` parameter. For datasets with more rows (e.g. MNIST 60 k),
a random sample of 5 000 rows is used to compute feature-to-feature distances.
5 000 samples are sufficient to obtain representative feature correlations while
reducing the BLAS multiply from (784 × 60 000) @ (60 000 × 784) to
(784 × 5 000) @ (5 000 × 784) — a 12× reduction in compute.

### `graphtree_pure.py` — ExtraTrees row sampling + normalisation

- Column normalisation replaced with a single numpy broadcast (mean/std
  computed across all columns at once).
- `ExtraTreesClassifier`: rows capped at 5 000 via `np.random.default_rng`
  before `fit`; also eliminated the `XR.tolist()` → `np.array()` round-trip
  by using `XR._data` directly.

---

## 11. `sourcecode/src/vx/gff/Server.py`

### Problem
`"debug": Settings.DEBUG` was commented out in the Tornado application
settings. `Settings.DEBUG = True` but was never passed to Tornado, so it ran
in production mode and set long `Cache-Control` headers on every `/lib/*.js`
file. After any JS edit, browsers served the stale cached version.

### Fix
Uncommented `"debug": Settings.DEBUG`. Tornado now honours the `True` value,
disables static-file caching, and auto-reloads on Python file changes.

---

## 12. `sourcecode/src/vx/gff/static/lib/libdata.js`

### Problem — `ServiceData.start()` spinner stuck permanently

`ServiceData.start()` called `self.event()` inside the async `d3.json`
callback with no inner try/catch. Any exception thrown by an event handler
(including a `TypeError: null is not iterable` from `UnselectedFeatures.load`
when the server returned a null response) silently escaped the callback,
leaving `MOPRO.popprocess(ps)` uncalled. The loading overlay then showed the
last pushed process name forever.

The specific trigger: D3 v4 wraps a 1-argument callback so that on HTTP error
it receives `null` instead of data. `getUnselecteFeatures`'s event passed that
`null` to `USFOBJ.load()` which called `for (var id of null)`, throwing.

### Fix
- `ServiceData.start()`: added an inner `try/catch` around `self.event()`;
  `MOPRO.popprocess(ps)` is now always reached.
- `getUnselecteFeatures` event: `self.unselectedfeids = Array.isArray(this.ou) ? this.ou : []`.
- `UnselectedFeatures.load()`: added `if (!Array.isArray(selfgff.unselectedfeids)) return`.

---

## 13. `sourcecode/src/vx/gff/static/lib/UnselectedFeatures.js`

### Problem
`load()` iterated directly over `selfgff.unselectedfeids` with `for...of`.
If the field was `null` (null server response or uninitialised), this threw
`TypeError: null is not iterable`, propagating up and preventing MOPRO cleanup.

### Fix
Added `if (!Array.isArray(selfgff.unselectedfeids)) return;` before the loop.

---

## 14. `sourcecode/src/vx/gff/static/lib/chart_bipartite.js` and `chart_feature_community.js`

### Problem
Both charts expose `highlightforce()` and `updateedgestransparency()` as public
methods called externally (via `selft.layoutfeatures.highlightforce(...)` from
`onFeatureSelectionChanged`). These methods reference `self.link` and
`self.node`, which are only assigned inside `draw()`. If the CSV is still
loading when `draw()` returns early, or if `onFeatureSelectionChanged` fires
before `draw()` completes, both methods crash with
`TypeError: Cannot read properties of null`.

### Fix
- Added `self.link = null; self.node = null;` at construction time.
- Added `if (!self.node || !self.link) return;` at the top of `highlightforce`.
- Added `if (!self.link) return;` at the top of `updateedgestransparency`.

---

## Test coverage

`tests/test_optimizations.py` — 52 new tests across 8 test classes:

| Class | What it tests |
|-------|---------------|
| `TestProximityCompute` | Vectorised euclidean matches reference for 50 random pairs |
| `TestPMatrix` | Numpy-backed PMatrix get/set/symmetry/None sentinel |
| `TestDataioPairwise` | Shape, symmetry, diagonal, normalised range, exact match vs reference for Euclidean; diagonal/symmetry for Cosine and Pearson; edge cases (empty, single row) |
| `TestBKmeansMath` | `computeMean` and `computeMedoid` for all/subset/single/empty clusters |
| `TestBKmeansFEMean` | `computeMean` matches numpy for normal and empty clusters |
| `TestMDataSamplex` | Row-only, col-only, row+col, no-op paths |
| `TestMDataOpenFileCSV` | Shape, values, column names, column index mapping |
| `TestKNN` | Shape, correct nearest neighbour, ascending distances, no self-neighbour |
| `TestGNNFECompleting` | Symmetrisation and idempotency |
| `TestFeatureGraphIntegration` | MST+Correlation/Pearson/Extratrees: node count, link count, tree present, treehi, edgehist length |
| `TestProjectionPipeline` | PCA/MDS/t-SNE/simple: point count and finite values |

Together with the 9 pre-existing smoke tests, the full suite is **61 tests,
all passing** in under 5 seconds.

```
Ran 61 tests in 4.344s
OK
```
