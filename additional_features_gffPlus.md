# GFF+ Additional Features

This file tracks the lightweight extensions and performance work added on top of the original GFF application.

## Bug Fixes

- **Bipartite graph stuck on "get unselected features"**
  - Root cause: `ServiceData.start()` called `self.event()` asynchronously with
    no inner try/catch. Any exception (e.g. null server response) silently
    escaped, leaving `MOPRO.popprocess()` uncalled and the loading overlay
    frozen permanently.
  - `ServiceData.start()` now wraps `self.event()` in an inner try/catch so
    `MOPRO.popprocess(ps)` is always called regardless of what the event handler
    does.
  - `getUnselecteFeatures` event now defaults a null/missing server response to
    `[]` before passing it to `USFOBJ`.
  - `UnselectedFeatures.load()` now guards against `null` with
    `if (!Array.isArray(...)) return` before the `for...of` loop.

- **Tornado serving stale JS after edits**
  - `"debug": Settings.DEBUG` was commented out in `Server.py`, so Tornado ran
    without debug mode and set aggressive `Cache-Control` headers on `/lib/*.js`.
    Browsers served the old files even after on-disk changes.
  - Re-enabled `"debug": Settings.DEBUG` (value is `True`). Tornado now sets
    no-cache headers on static files, so edits are picked up on the next
    normal page load.

- **`chart_bipartite` and `chart_feature_community` crash before draw**
  - Both charts call `highlightforce()` and `updateedgestransparency()` as
    public methods (triggered by `onFeatureSelectionChanged`) before `draw()`
    has populated `self.link` and `self.node`.
  - Added `self.link = null` / `self.node = null` initialisers at construction
    and early-return guards at the top of both methods.

- **favicon.ico returning 404**
  - `RedirectHandler` for `/favicon.ico` returned 404 intermittently.
  - Replaced with a `FaviconHandler(StaticFileHandler)` subclass that serves
    `icon.png` directly without a redirect.

- **`saveprojection` KeyError when feature graph not yet built**
  - `r["configfeature"]["ranking"]` and `["nodes"]` crashed when a user
    triggered instance projection before the feature graph existed.
  - Changed to `.get("ranking", [])` / `.get("nodes", [])`.

- **`makeInstancesLabels` unclosed file handle on IndexError**
  - If `colid` was out of range the file opened for the CSV header was never
    closed. Replaced `open/close` with a `with` block.

- **NJ algorithm hangs indefinitely on wide datasets**
  - Neighbour-Joining is O(n³). For MNIST (784 features) it never finishes.
  - When N > 300 and algorithm is NJ, `make_graph` now silently falls back to
    MST instead.

- **`getfeatureselected` TypeError on first dataset open**
  - `self.getNode(i).label` threw `TypeError` when `graph.nodes` was still
    empty. Added a null guard that skips nodes not yet loaded.

- **Silent failure on `statusopt=2`**
  - When `processFeatures` or `processInstances` failed on the server, the
    browser only called `console.log("error")` — no user-visible feedback.
  - Now displays `"Error building feature graph"` / `"Error building
    projection"` in the relevant status panels.

- **MNIST feature graph taking 15+ seconds**
  - Three compounded bottlenecks caused this:
  
  1. `feature_importances_` accessed 784 times in a loop. The sklearn property
     uses `Parallel(n_jobs=-1)` internally; on Windows each access
     created and tore down a process pool. 784 cycles = 14 s overhead.
     Fixed by caching the property in a variable once outside the loop.
  
  2. `DataMatrix` loaded all 60 000 rows (168 MB) before any computation.
     Added `max_rows=5000` to `DataMatrix`, so only 5 000 rows are read
     from disk. Feature graph computation uses this capped loader; instance
     projection still uses the full file.
  
  3. Pearson/Correlation target loop made 784 separate `proximity_cols`
     function calls. Replaced with `_target_correlations` helper that
     computes all correlations in a single `data.T @ target` matrix multiply.
  
  4. N² MST edge-construction loop called `pm_t.getValue(i,j)` 307 k times.
     Replaced with `np.triu_indices` + numpy fancy indexing + a new
     `_kruskal_mst` function that accepts a pre-sorted edge list.

- **Browser loading 168 MB CSV via `d3.csv` (30+ seconds)**
  - `loadfilecsv` requested the full `transform.csv` from the server, forcing
    the browser to download and parse 168 MB of CSV.
  - `Query.savefile` now creates a `sample.csv` (first 5 000 rows, ~14 MB)
    at upload time. `loadfilecsv` loads `sample.csv` instead. A new type=25
    server endpoint (`ensureSampleCsv`) generates `sample.csv` on demand for
    datasets uploaded before this fix.
  - Browser load time: 30+ s → ~0.5–1 s.

- **MNIST projection loading all 785 columns for small selections**
  - `MakeProjection` now asks `DataMatrix` to load only the selected feature
    columns plus the target column when a feature subset is active.
  - `DataMatrix` preserves original feature ids while storing numeric matrices
    as `float32`, halving baseline matrix memory.
  - Zero-variance selected pixels now produce a stable all-zero projection
    instead of sklearn PCA warnings.

## Added

- **UpSet feature layout**
  - Adds a scalable set/intersection view for selected or high-ranked features.
  - Intended replacement for large Venn diagrams when more than about 5 sets are involved.
  - Uses the existing CSV data and feature-selection workflow.

- **Bundle feature layout**
  - Exposes a GFF-compatible circular edge-bundle view for feature relationships.
  - Supports click selection, hover highlighting, and the existing toolbar selection counters.

- **Feature heatmap layout**
  - Adds a tree-ordered feature similarity matrix.
  - Helps inspect dense feature-feature relationships without relying only on node-link layouts.
  - Clicking a cell selects the two related features and reuses the existing instance projection workflow.

- **Community feature graph**
  - Detects lightweight feature communities from strong feature graph relationships.
  - Collapses related features into supernodes sized by member count and colored by average relevance.
  - Clicking a community selects its representative member features for the existing projection workflow.

- **Bipartite feature-instance graph**
  - Links selected or high-ranked feature nodes to representative active instances.
  - Helps explain how chosen features connect to the rows/items they activate.
  - Uses cached `transform.csv` data and keeps the graph sampled for responsiveness.

- **Additional instance projections**
  - Re-enabled **PCA** and **MDS** in the projection dropdown.
  - Hardened PCA/MDS handling for empty and tiny datasets.

- **Local XAI feature scoring**
  - Adds a CPU-first backend XAI pipeline that works on existing uploaded
    `transform.csv` files.
  - New query type `26` runs the pipeline and saves results as `xai.obj` beside
    `feature.obj` and `instance.obj`.
  - Uses lightweight sklearn ExtraTrees models by default:
    `ExtraTreesClassifier` for categorical targets and `ExtraTreesRegressor`
    for continuous targets.
  - Computes model feature importance and permutation importance locally.
  - Computes SHAP summaries and a SHAP similarity graph only when `shap` is
    installed; otherwise SHAP is skipped and the core importance results still
    return successfully.
  - The JSON payload includes feature names, raw and normalised importance
    scores, permutation scores, optional SHAP summaries, target metadata, model
    type, adaptive CPU settings, and status.

- **XAI feature graph controls**
  - Added toolbar controls for running local XAI, colouring nodes by XAI
    importance, sizing nodes by XAI importance, threshold-selecting important
    features, and switching to a SHAP similarity graph when SHAP data exists.
  - Existing feature relevance graph modes remain available; XAI is an
    alternate node metric rather than a replacement for the original GFF graph.

## Performance And Lightweight Work

- **Browser CSV caching**
  - Avoids reloading the same `transform.csv` repeatedly when switching views or refreshing the pair/intersection visualizations.

- **Lighter graph payloads**
  - Stores the MST/NJ tree edges plus a capped number of non-tree relationship edges.
  - Keeps histograms useful while avoiding very large `feature.obj` files on wide datasets.

- **Faster MST construction**
  - Uses a sorted in-memory edge list instead of `PriorityQueue` for Kruskal MST construction.

- **Adaptive projection fallback**
  - Very large instance counts automatically use PCA instead of expensive exact t-SNE/MDS/UMAP-style paths.

- **Lightweight interaction mode**
  - PCA is now the default instance projection because it is fast and suitable for interactive feature selection.
  - Expensive methods such as t-SNE, UMAP, MDS, and LSP no longer recompute automatically on every feature click.
  - Users can still run those methods explicitly with the instance visualization execute button.

- **Duplicate projection skip**
  - Repeated projection requests with the same selected features, target, projection, and label configuration reuse the existing `instance.obj`.
  - This prevents unnecessary recomputation from repeated clicks or refreshes.

- **Selected-column projection loading**
  - Instance projection no longer reads every MNIST pixel column when the user
    selected only a subset. The loader reads the active features plus the
    target label and keeps the original id mapping for graph selections.

- **Mouse-wheel zoom for new graph layouts**
  - Added zoom/pan support to Bundle, Heatmap, Community, Bipartite, and UpSet layouts.
  - This keeps dense graph views usable without changing the existing Force layout behavior.

- **Faster Bipartite graph preview**
  - Bipartite now scans a bounded stride sample of large CSV files instead of every row.
  - Rendered representative instances are capped to keep force simulation responsive.
  - Instance labels are loaded lazily and capped, so opening the Bipartite view no longer waits on the full original CSV label column.

- **Quieter/faster projection backends**
  - UMAP is configured for lower-memory, parallel execution without the random-state warning.
  - MDS uses fewer initializations/iterations for exploratory speed while staying single-process on Windows.
  - Debug timing prints were removed from the normal projection path.

- **Adaptive CPU mode for XAI**
  - XAI automatically chooses training rows, number of trees, permutation rows,
    permutation repeats, and SHAP rows from dataset width/row count and
    available-memory signals when available.
  - Defaults are deliberately CPU-safe and Windows-friendly:
    `n_jobs=1`, bounded samples, and reduced permutation work on wide datasets.
  - Users can override `xai_estimators`, `xai_train_rows`,
    `xai_permutation_rows`, `xai_permutation_repeats`, `xai_shap_rows`, and
    `xai_n_jobs` through the API for controlled experiments.
  - Quantization is left as a future hook only; the current implementation uses
    sklearn tree models, not local neural or LLM models.

## Planned

- UI hint in the instance panel showing when a projection was automatically
  switched to a faster method (e.g. t-SNE → PCA for large datasets).
- Expose the row-sampling cap (`max_rows=5000` in `proximitymatrix_cols` and
  the ExtraTrees fit) as a user-visible setting for power users who need finer
  control over accuracy vs. speed.

## Graph Methods That Align With GFF

These methods preserve the central idea of the project: features are graph nodes, edges encode feature relationships, and graph exploration supports feature selection.

- **MST / NJ feature graphs**
  - Existing core method.
  - Best for global structure and tree-based overview.

- **Circular edge bundle**
  - Best for seeing graph relationships while reducing edge crossing clutter.
  - Works well as a companion to the Force layout.

- **Tree-ordered heatmap**
  - Best for dense feature-feature comparisons.
  - Keeps the GFF tree order but exposes pairwise relation strength in a compact grid.

- **Community graph**
  - Detects feature modules directly from strong feature relationships.
  - Collapses related features into supernodes for a lighter overview.
  - Useful for finding redundant or functionally similar feature groups before projection.

- **Bipartite feature-instance graph**
  - Links selected features to representative instances where those features are active.
  - Useful for explaining why selected feature groups affect instance projections.
  - Provides a bridge between the feature graph and the instance view.

- **UpSet/intersection graph**
  - Best replacement for large Venn diagrams.
  - Useful when selected features define overlapping instance groups.

## AI / XAI Direction

The most useful AI layer for this project is not a chatbot pasted onto the UI. It should be an explainable feature-analysis assistant that produces scores, groups, and explanations that can be visualized as graph attributes.

- **Model-based feature importance**
  - Implemented for local sklearn ExtraTrees models.
  - Adds model feature importance and permutation importance.
  - Optional SHAP summaries are added only when the `shap` package is present.
  - Visualizes XAI importance as node color/size and supports threshold selection.

- **SHAP feature graph**
  - Implemented as an optional graph mode when SHAP values are available.
  - Edges connect features with similar SHAP contribution profiles.
  - This gives a graph of features that behave similarly in the model, not only features that are statistically similar in raw data.

- **Local explanation mode**
  - User selects a point or lasso group in the instance projection.
  - GFF+ explains which selected features contributed most to that instance/group.
  - Output should highlight the relevant nodes in the feature graph.

- **Counterfactual feature suggestions**
  - For a selected class or cluster, suggest features that would most separate it from others.
  - Useful for supervised exploratory analysis and feature subset refinement.

- **AI-assisted graph summary**
  - Generate a short textual summary from computed metrics: important feature groups, redundant features, contradictory/opposite features, and target-correlated regions.
  - This can be implemented without sending private data outside the app by summarizing computed statistics locally.

## Practical XAI Implementation Status

Done:

1. Backend XAI endpoint trains a lightweight sklearn model on the target.
2. Returns feature importance, permutation importance, and optional SHAP values when `shap` is installed.
3. Stores XAI results beside `feature.obj` as `xai.obj`.
4. Adds **XAI Importance** color and size modes for feature graph nodes.
5. Adds threshold filtering from XAI importance.
6. Adds a **SHAP Similarity Graph** mode when SHAP explanation profiles exist.
7. Adds adaptive CPU mode for sample sizes, trees, permutation repeats, SHAP sample size, and single-process Windows-safe execution.

Next:

1. Add local/group explanation from selected projected instances back to highlighted graph nodes.
2. Add counterfactual feature suggestions for selected classes or clusters.
3. Add local textual summaries from computed statistics without sending data to external services.

## Implemented Layout Codes

- `fo`: Force/radial GFF graph
- `cb`: Circular bundle graph
- `sb`: Sunburst tree graph
- `pk`: Circle pack tree graph
- `hm`: Tree-ordered feature heatmap
- `cm`: Feature community graph
- `bp`: Bipartite feature-instance graph
- `up`: UpSet/intersection graph
