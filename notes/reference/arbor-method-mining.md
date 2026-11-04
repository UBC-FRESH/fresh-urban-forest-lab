# Arbor method mining and clean-room point-cloud primitives

Status: reference note, 2026-11-03. Phase P12.

This note records the first audit of [`r-lidar/arbor`](https://github.com/r-lidar/arbor)
for methods, algorithms, and design patterns that this MIT-licensed project can
reimplement. It is a **method-mining** note, not a code-copying plan.

Source snapshot:

- Repository: `https://github.com/r-lidar/arbor`
- Version: `v1.1.5`
- Commit inspected: `a2b487f4a23236a42eec50cb6583a5eae15593ed` (2026-11-02)
- Package licence: **GPL-3.0**
- Book: `https://r-lidar.github.io/arbor_book/`
- Manual: `https://r-lidar.r-universe.dev/arbor/doc/manual.html`

## Why this note exists

Arbor is a strong, production-oriented implementation of an MLS/TLS forest point-cloud
pipeline. Its book explains the algorithms and design choices clearly. We want the ideas,
not the GPL code.

The repository rule is already explicit in `AGENTS.md`: do not copy copyleft code;
reimplement the published method and cite it. This note applies that rule to Arbor and
keeps the provenance in one place.

## Licence posture

1. Arbor's R/C++ package is GPL-3.0. No Arbor code is copied into this MIT repository.
2. We mine methods, algorithms, data contracts, and design patterns. The Python
   implementation is written from the book, manual, and published papers, with our own
   structure, names, tests, and documentation.
3. The book text and figures are not copied. We summarize the method in our own words.
4. Some Arbor vendored components are MIT (PTD, DBSCAN, libqsm, libqsf, robust
   predicates). That does not make the whole package MIT. We do not vendor them by
   default.
5. If a future change wants to copy a specific code block instead of reimplementing it,
   the change stops for a licence review. It does not enter an MIT package by accident.

This is engineering policy, not legal advice.

## Arbor is MLS/TLS, not ALS

Arbor targets mobile laser scanning (MLS) and terrestrial laser scanning (TLS). Its book
says the point cloud must not be normalized, ground classification is critical, and the
pathfinder depends on geometric continuity from the ground through trunks and branches.

That is not the airborne laser scanning (ALS) setting behind LidarBC and raw ALC/ALS point
clouds. ALS is top-down, sparse in the lower stem, and often already classified. The
transferable ALS pieces are data conditioning and ground classification, not the
pathfinder/QSM stack.

The QSM and semantic/instance material is a future MLS/TLS lane.

## Candidate inventory

Complexity is a rough estimate for a clean Python implementation with tests, not a comment
on Arbor's code.

### Data conditioning

| ID | Candidate | Arbor source | What it does | Why it matters here | Complexity | Status |
| --- | --- | --- | --- | --- | --- | --- |
| D1 | Hybrid homogenization | `R/segment_decimation.R`, `src/utils/homogeneization.cpp`, book ch. 3 | Barycentric voxel decimation plus deterministic reinjection of about 10% of discarded points | Homogenizes uneven scans without amplifying noise as much as plain voxel thinning | Low | Implemented in `pointcloud.py` |
| D2 | Statistical outlier removal (SOR) | `src/utils/sor.cpp` | Mean kNN distance per point, global mean/SD threshold | Cheap noise filter before CHM/ITD | Low | Implemented in `pointcloud.py` |
| D3 | Voxel connected components | `src/utils/Grid3D.cpp` | Sparse voxel labelling with 6/18/26 connectivity | Clean small clusters and merge fragments | Low | Implemented in `pointcloud.py` |
| D4 | Local anisotropy wood likelihood | `src/utils/anisotopy.cpp`, `R/segment_anisotropy.R`, book ch. 5 | kNN covariance eigenvalues; `(lmax - lmin) / lmax` | Cheap wood/foliage descriptor and branch detector | Low-medium | Implemented in `pointcloud.py` |
| D5 | 3D radius smoothing | `src/utils/smooth3d.cpp` | Replace each point by the mean of neighbours inside a radius | Simple denoising / skeleton smoothing | Low | Candidate |
| D6 | Low-point cut and HAG handling | `R/segment_ground.R`, book ch. 4 | Ignore points below a configurable HAG while keeping them in the cloud | Avoids ground/grass continuity in segmentation | Low | Candidate |

### Ground and terrain

| ID | Candidate | Arbor source | What it does | Why it matters here | Complexity | Status |
| --- | --- | --- | --- | --- | --- | --- |
| G1 | Progressive TIN densification (PTD) | `src/segment/segment_ground_api.cpp`, `src/vendor/ptd/PTD.cpp`, book ch. 4 | Sparse ground seed, iterative TIN densification under angle/distance thresholds, ground class and HAG | Directly relevant to unclassified or inconsistently classified LidarBC/ALS tiles | Medium-high | Implemented as simplified `classify_ground_ptd` in P13.1 |
| G2 | TIN interpolation and 1-NN fallback | `src/segment/segment_ground_api.cpp` | Interpolate ground elevation on the TIN; nearest ground point outside the TIN | Robust HAG at tile edges and sparse coverage | Medium | Implemented as part of P13.1; real-tile edge validation pending |
| G3 | Ground QA and low-outlier handling | Book ch. 4 | Record low-point cut, ground class, and HAG assumptions | Makes ground classification auditable | Low | Seed/iteration counters implemented; low-point-cut policy pending P13.3 |

Underlying method to cite for PTD: Axelsson (2000), adaptive TIN models. Arbor's vendored
PTD implementation is MIT, but the planned implementation is a new Python version.

### Semantic and instance segmentation

| ID | Candidate | Arbor source | What it does | Why it matters here | Complexity | Status |
| --- | --- | --- | --- | --- | --- | --- |
| S1 | KNN pathfinder graph | `src/segment/GraphBuilder.cpp`, `src/segment/Graph.cpp`, book ch. 5-6 | kNN graph; cost = distance^power × angle penalty × semantic penalty; Dijkstra to ground or seeds | Core Arbor idea for continuous wood and tree instances; MLS/TLS only | High | Future MLS/TLS lane |
| S2 | Passage accumulation | `src/segment/segment_semantic_api.cpp` | Count shortest paths through each node; threshold to a skeleton | O(N) subtree accumulation instead of one path walk per target | Medium-high | Future MLS/TLS lane |
| S3 | Seed detection | `src/seed/SeedDetector.cpp`, `R/seeds_find.R`, book ch. 6 | Wood slices, RANSAC circles, cages, connected components, short-passage merging | Finds stems for instance segmentation | High | Future MLS/TLS lane |
| S4 | Over-segmentation resolver | `src/segment/segment_overfitting.cpp`, `R/segment_overfitting.R`, book ch. 6.4 | Layered DBSCAN, circle fitting, match accumulation, union-find merge | Useful post-processing for CHM-based ITD too | High | Candidate |
| S5 | Buffer and small-tree flags | `R/segment_flag.R`, book ch. 6.5-6.6 | Flag edge trees and small instances without deleting points | Directly useful for CHM/ITD edge artifacts and understory | Low | Candidate |

### QSM and QSF

| ID | Candidate | Arbor source | What it does | Why it matters here | Complexity | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Q1 | Orbicular cross-section fitting | `src/fitting/*`, book ch. 7.1 | RANSAC circle/ellipse/Fourier/multi-circle fits; area-equivalent circle | Robust DBH and branch diameter on noisy scans | Medium-high | Future QSM lane |
| Q2 | Geodesic layering + DBSCAN skeleton | `src/qsm/QSMbuilder_cluster.cpp`, `QSMbuilder_skeleton.cpp`, book ch. 7.2 | Layer by geodesic distance to ground, DBSCAN within layers, greedy chain-growing skeleton | QSM skeleton method; inspired by aRchi | High | Future QSM lane |
| Q3 | Pre-shot allometric QSM | `src/qsm/QSMbuilder_radius.cpp`, book ch. 7.3 | Cheap allometric prior to prune unmeasurable cylinders | Strong pattern: cheap prior to skip expensive work | Medium | Future QSM lane |
| Q4 | Radius measurement, interpolation, pipe model | `src/qsm/QSMbuilder_radius.cpp`, `QSMbuilder_pipemodel.cpp`, book ch. 7.4 | Measure where possible, interpolate gaps, reconstruct unmeasured branches | Separates measured, interpolated, and reconstructed volume | High | Future QSM lane |
| Q5 | Quality codes and filters | `R/qsm_*`, `R/qsf_filter.R`, book ch. 7.9, 8.2 | Per-cylinder quality 0-5, per-tree warnings, QSF filters | Honest reporting of what was measured versus modelled | Medium | Future QSM lane |
| Q6 | QSF batch orchestration | `R/qsf.R`, `R/qsf_log.R`, book ch. 8 | Parallel one-QSM-per-tree with per-tree logs and filters | Good pattern for batch science jobs with per-item provenance | Medium | Future QSM lane |

### Allometry and fallback

| ID | Candidate | Arbor source | What it does | Why it matters here | Complexity | Status |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | Height-to-DBH allometric prior | `src/utils/allometry.*`, book ch. 7.3, 7.6 | Predict DBH from height; use only as a prior and fallback | Explicit allometric fallback with a warning, never silently a measurement | Medium | Future QSM lane |
| A2 | Allometry database with references | `R/allometry.R`, `src/utils/allometry.h` | Named models with author, country, and DOI/reference | Reinforces the existing allometry provenance discipline | Low-medium | Candidate |

The default Arbor prior cites Griese et al. (2025), *Scientific Data* 12:1953,
`https://doi.org/10.1038/s41597-025-06421-7`. Cite the paper; do not copy its tables.

## Design patterns worth adopting

1. **Staged pipeline with explicit contracts.** Ground/HAG, wood likelihood, semantic
   label, instance ID, and QSM are separate contracts. Keep the frozen-dataclass
   discipline.
2. **Parameterless defaults, few escape hatches.** A production pipeline should work out
   of the box. Expose only parameters a user can reason about.
3. **Per-stage and per-item QA.** Ground QA, segmentation QA, QSM quality codes, and
   per-tree logs. Do not let one scalar hide the method or the failure mode.
4. **Measured / interpolated / reconstructed distinction.** Arbor's QSM quality codes are
   a good model. Report the fractions, not just the total.
5. **Flag, do not silently delete, edge trees.** Apply the same idea to CHM/ITD products.
6. **Deterministic randomness and tie-breaking.** Required for reproducible tests and
   cross-platform outputs.
7. **Memory-aware graph representation.** CSR-like rows, chunked kNN, and explicit cache
   release. Python equivalents: `scipy.sparse`, `cKDTree` chunks, no full pairwise matrix.
8. **Cheap prior to prune expensive work.** Build a cheap model, use it to skip hopeless
   cases, and record that it was only a prior.
9. **Batch with per-item logs.** Keep thousands of per-tree warnings in a queryable log
   rather than flooding the console.
10. **Provenance in the output.** Record model names and references, not just numbers.

## What not to copy

- Arbor's GPL-3.0 R/C++ glue.
- Vendored C++ libraries as a shortcut, even the MIT ones. They add a C++ build, a second
  licence surface, and maintenance burden.
- aRchi code. aRchi is CeCILL (copyleft). Cite Martin-Ducup et al. (2020) and reimplement.
- lidR code. GPL-3.0. Use `laspy`/`scipy` or reimplement.
- The Arbor book prose or figures.
- Allometric coefficient tables without checking their data terms.

## Implemented in this phase

`src/fresh_urban_forest/pointcloud.py` contains the four low-risk primitives:

- `hybrid_homogenize`: BVD plus deterministic reinjection.
- `statistical_outlier_mask`: SOR outlier flag.
- `voxel_connected_components`: sparse 6/18/26 voxel labelling.
- `local_anisotropy`: kNN covariance anisotropy.

They are opt-in utilities. They are not wired into the default CHM/ITD pipeline.

Each function carries a `Method provenance` docstring section naming Arbor 1.1.5, the
source file or book chapter, the GPL-3.0 source licence, and the clean-room statement.

## ALS ground classification (P13.1-P13.2)

`classify_ground_ptd` is the first ALS-specific function. It seeds a TIN from the lowest
point in each grid cell, then progressively adds points whose vertical residual from the
TIN is within `max_distance_m` and whose point-to-triangle-vertex angle is within
`max_angle_deg`. The final TIN provides `ground_elevation` and `height_above_ground`.

This is a **simplified, PTD-inspired** implementation, not a line-by-line port:

- the angle test uses the maximum point-to-triangle-vertex angle measured from the triangle
  plane, not the full multi-pass PTD angle logic;
- the default vertical residual is permissive (2 m);
- points outside the TIN hull are not classified as ground; their HAG uses the nearest
  support point;
- the TIN support is thinned to 200,000 points for large tiles;
- a degenerate TIN returns the seed-only result with a warning.

The synthetic fixtures cover a flat plane, a gentle slope, a high outlier, a collinear
degenerate seed set, an empty cloud, and invalid parameters.

P13.2 validates a 415,068-point LidarBC 2025 tile
(`bc_092g024_4_3_1_xyes_8_utm10_20250826_20250826.laz`, EPSG:3157, OGL-BC). At the strict
setting, class-2 recall is 0.9998 and class-2 HAG p99 is 0.021 m. The tile's class 1 is
unclassified and class 7 is noise, so neither is a valid negative set. About 80% of class-7
near-ground noise is labelled ground; the high-noise tail is not. Precision against class 2
is therefore not an accuracy estimate. See `notes/reports/p13-als-ground-validation.md`.

**Do not use this as an operational ground classifier yet.** P13.3 must add a low-point cut
and SOR pre-pass and validate across more tiles and a checked reference patch.

## Next slices

1. **P13.3 low-point-cut/SOR preprocessing**: remove near-ground noise before PTD, then
   re-run this tile and a second tile.
2. **CHM/ITD post-processing**: buffer flags, small-tree flags, and over-segmentation
   merging.
3. **MLS/TLS semantic and instance segmentation**: a future `fresh-pointcloud` package,
   not this app's core.
4. **QSM/QSF**: the same future package, with measured/interpolated/reconstructed
   reporting and quality codes.

## Attribution template

### Module docstring

```python
"""Hybrid voxel homogenization for forest point clouds.

Method provenance
-----------------
Idea and algorithm: Arbor 1.1.5 (r-lidar/arbor), commit
``a2b487f4a23236a42eec50cb6583a5eae15593ed``, book chapter 3
(https://r-lidar.github.io/arbor_book/decimation.html).
Source licence: GPL-3.0. This is an independent Python reimplementation;
no Arbor source code was copied.
"""
```

### Project note row

```markdown
| Method | Source | Licence | What we took | What we did not take |
| --- | --- | --- | --- | --- |
| Hybrid homogenization | Arbor 1.1.5, book ch. 3 | GPL-3.0 (method/idea) | BVD + 10% reinjection | No C++/R code; new Python implementation |
```

### Sphinx page

```rst
Hybrid homogenization
---------------------

We reimplemented the barycentric-voxel-decimation and random-reinjection idea
described in the Arbor book (Arbor 1.1.5, chapter 3). Arbor is GPL-3.0; this
project is MIT, so the implementation is an independent Python version and no
Arbor source code was copied.
```

### Citation block

```text
Roussel, J.-R. (2026). Arbor: Tree Segmentation in MLS/TLS Point Clouds
(version 1.1.5) [Computer software]. https://github.com/r-lidar/arbor

Roussel, J.-R. (2026). Arbor: The Complete R Tutorial Book.
https://r-lidar.github.io/arbor_book/
```

## References

- Arbor repository: `https://github.com/r-lidar/arbor` (GPL-3.0, v1.1.5, commit
  `a2b487f4a23236a42eec50cb6583a5eae15593ed`)
- Arbor book: `https://r-lidar.github.io/arbor_book/`
- Arbor manual: `https://r-lidar.r-universe.dev/arbor/doc/manual.html`
- Axelsson, P. (2000). DEM generation from laser scanner data using adaptive TIN models.
  *International Archives of Photogrammetry and Remote Sensing*, 33(B4/1), 110-117.
- Fischler, M. A., & Bolles, R. C. (1981). Random sample consensus. *Communications of
  the ACM*, 24(6), 381-395.
- Ester, M., Kriegel, H.-P., Sander, J., & Xu, X. (1996). A density-based algorithm for
  discovering clusters in large spatial databases with noise. *KDD-96*.
- Martin-Ducup, O., et al. (2020). Terrestrial laser scanning reveals convergence of tree
  architecture with increasingly dominant crown canopy position. *Functional Ecology*.
  `https://doi.org/10.1111/1365-2435.13678`
- Griese, N., Ritzert, M., & Nölke, N. (2025). A large dataset of labelled single tree
  point clouds, QSMs and tree graphs. *Scientific Data*, 12, 1953.
  `https://doi.org/10.1038/s41597-025-06421-7`
