# Algorithm audit and submodular shortlisting

Implementation on `advancements`. The supplied research reference
`submodular_efficient_(1).py` is intentionally excluded from the repository.
It contained Colab shell commands, hard-coded Fashion-MNIST paths, training at
import time, and ten manually repeated cluster selectors. It cannot run as a
normal Python module. Its facility-location selection idea is implemented in
`sourcecode/src/vx/com/py/sampling/Submodular.py`, without new dependencies.

## Use

In the instance projection toolbar, enter a **Representative rows** limit and
press Execute. Leave it blank to project all rows. Limits above the dataset
size retain all rows. Selection excludes the target, respects the active
feature subset and Euclidean/cosine choice, and preserves original instance
IDs and labels. The sample limit is included in projection cache comparisons.

Standalone CSV selection:

```sh
python shortlist_dataset.py input.csv subset.csv --size 1000 --target label
python shortlist_dataset.py input.csv features.csv --size 30 --target label --axis features
```

The CLI requires numeric selection columns. It retains the target in output.
For already computed module embeddings, call `shortlist(module_vectors, size)`;
each returned integer indexes an original module. Passing a data matrix
transposed selects representative feature profiles. This does not discover
biological modules or change the existing community detection layout.

## Objective and scaling

The objective is facility location: sum over reference items of their maximum
similarity to any selected item. Euclidean similarity is `1/(1 + distance)`;
cosine similarity is clipped to `[0, 1]`, with zero vectors contributing zero.
These are nonnegative coverage objectives. The implementation uses stochastic
greedy candidates and at most 512 uniformly sampled references, with seed 7.
It does not reproduce the notebook's per-cluster quotas: it selects a single
global budget and avoids rounding losses and hard-coded cluster counts.

`epsilon=0` evaluates all candidates; `max_reference >= len(X)` uses every
reference. Together these give ordinary greedy facility-location selection.
Defaults approximate the full-data objective; they do not guarantee class
balance, rare-group retention, or downstream prediction accuracy. Scale input
features beforehand when their units should have equal influence.

Distance working arrays are bounded by `batch_size * max_reference`, rather
than dataset size squared. Input data is still loaded into memory, including
a float64 conversion. Candidate scans also take O(n * budget) total work.
This is not an out-of-core loader. A local synthetic check selected 100 unique
rows from 20,000 x 32 Gaussian data in 0.24 seconds; this is not a real-data
quality evaluation or a general performance guarantee.

## Findings fixed

| Area | Finding | Change |
| --- | --- | --- |
| Sampling | Zero budget returned rows; FE random sampling was a no-op; global RNG was reset | Explicit empty result, local seeded sampling, FE implementation, unknown-method errors |
| Bisecting k-means, both implementations | `k > n` could loop forever; empty data crashed; `k=1` returned first row as centroid | Validate budgets/iterations and calculate initial centroid |
| Bisecting k-means, both implementations | Stable partitions still ran all iterations | Stop on unchanged membership |
| Exact KNN | Full quadratic distance storage and cancellation from squared norms at large offsets | Bounded row batches with direct distances; deterministic ties; reject negative k and unsupported metrics |
| MDS | Float32 conversion and squared-norm subtraction lost small distances at large offsets | Float64 direct pairwise distances |
| UMAP fallback | Single-feature PCA fallback could fail; output could be reported as spectral when PCA actually ran | Reuse guarded PCA and report actual fallback method |
| Projection | Reusing an object accumulated old points; sampling could misalign IDs/labels | Reset results, map source IDs and original labels, preserve full-data label offset |
| XAI preprocessing | Infinity without NaN escaped imputation; infinite targets reached estimator fitting | Impute all nonfinite feature values; discard nonfinite targets |
| NJ | Large-feature fallback to MST was silent in the payload | Include requested/used algorithm and fallback reason |

## Remaining limitations from inspection

- Feature graph and XAI loaders use a first-row cap. Sorted datasets can bias
  correlations, feature importance and class representation. The new projection
  selector does not change those loaders.
- XAI permutation importance is evaluated on training observations. Treat it
  as descriptive training-model importance, not held-out predictive evidence.
- MST still constructs a dense feature-distance matrix, NJ remains cubic below
  its cutoff, and exact KNN remains quadratic in distance computation despite
  its reduced working memory. Very wide feature graphs still need caution.
- LSP uses normal equations before an iterative fallback; conditioning and
  sparse factorization fill-in remain possible issues on difficult graphs.
- Legacy `Proximity.compute` still returns zero for unsupported metrics;
  KNN now validates its own metrics, but other legacy callers are unchanged.
- This audit covers the sampling/clustering, projection, graph-construction
  and XAI paths inspected here; it is not a proof of correctness of every
  legacy algorithm or browser visualization.

## Validation

Run `python -m unittest discover -s tests -q`. Added regressions cover greedy
objective optimality at each step, coverage of separated groups, unique and
repeatable selection, bounded distance batches, invalid budgets, clustering
centroids, duplicate neighbours, large-offset distances, UMAP fallback, XAI
infinity handling and projection ID/label alignment and object reuse.
JavaScript syntax is checked with Node. Browser interaction has not been
automated. Existing sklearn MDS deprecation warnings remain.
