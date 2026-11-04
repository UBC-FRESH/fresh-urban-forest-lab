# P15 manual ground reference patch and adapter design

Date: 2026-11-04
Phase: P15
Parent issue: #95
Tasks: #96, #97, #98
Status: patch checked; adapter design accepted; implementation not started

## P15.1 Manually checked 20 m reference patch

Patch source: `bc_082n025_4_2_1_xyes_8_utm11_2021.laz` (Golden-area 2021, steep,
EPSG:2955 + CGVD2013, OGL-BC).

- Center: E 496582.375, N 5678993.665.
- Extent: 20 m x 20 m, bounds E 496572.38-E 496592.37, N 5678990.20-E 5679003.66.
- Points: 6,393.
- Classes: 1 = 5,410; 2 = 975; 7 = 8.
- Side view: `runtime/p15/reference_patch.png` (not tracked).

### Manual check

The side view was inspected directly. Class 2 (blue) forms the lowest continuous surface.
Class 1 (gray) includes both above-surface vegetation/structure and a near-surface
unclassified band. Class 7 (red) is sparse.

What the check supports:

- class 2 is a coherent ground surface in this patch;
- the high points above that surface are not ground;
- class 1 is not a clean negative label because it mixes unclassified ground and vegetation.

What the check does **not** support:

- point-by-point labels for every class-1 point;
- a claim that class 2 is exhaustive;
- a full-tile or multi-tile accuracy claim.

### Patch metrics

Reference construction: class 2 positive; high-confidence negative = non-class-2 with
reference HAG > 2 m; ambiguous 0-2 m band excluded.

| Metric | Value |
| --- | ---: |
| Positive class 2 | 975 |
| High-confidence negative | 1,235 |
| Ambiguous 0-2 m | 4,183 |
| SOR removed | 227 |
| Predicted ground | 4,497 (72.93% of kept) |
| Class-2 recall | 0.950668 |
| High-confidence false-ground | 34 / 1,083 |
| High-confidence false-ground rate | 3.14% |
| Class-2 HAG p95 | 0.0024 m |
| Class-2 HAG p99 | 0.0434 m |
| Low-point flag on false ground | 52.9% |
| PTD iterations | 8 |
| Seed points | 224 |
| Warning | none |

The patch result is consistent with the full steep tile: recall about 95%, high-confidence
false-ground about 3%, and tight class-2 HAG. The low-point flag catches about half of the
false ground in this patch; it is a downstream guard, not a correction.

## P15.2 Optional FEMIC adapter design

The design is in `notes/design/femic-ground-adapter.md` and ADR 0007.

Summary:

- optional sidecar adapter, not a default FEMIC product;
- input: one LAZ/COPC tile plus explicit parameters;
- output: a ground LAZ with extra dimensions, a manifest, and a QA JSON;
- no hard FEMIC dependency and no core import;
- versioned schema, parameter hash, input/output hash, and provenance;
- contract tests on a small synthetic LAZ plus a golden-tile smoke test;
- warnings for missing CRS/vertical datum, degenerate TIN, low class-2 support, and
  unresolved noise.

## P15.3 Decision

Accept the optional adapter design. Do not implement it in this phase.

The classifier remains opt-in. The adapter is a sidecar contract, not a change to FEMIC's
default products. Implementation is a later, separate phase with its own tests and a
versioned contract.

## Limits

- The patch is 20 m x 20 m and visually checked, not point-by-point labelled.
- The ambiguous 0-2 m band is excluded from the negative set.
- One steep tile and one coastal tile are not a full terrain suite.
- The adapter design has not been implemented or contract-tested yet.
