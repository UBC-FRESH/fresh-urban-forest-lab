# P21 ground-adapter second-tile smoke test

Date: 2026-11-04
Phase: P21
Parent issue: #126
Task: #127
Status: smoke test complete; adapter unchanged

## Tiles

| Tile | Setting | Points | CRS | Vertical datum |
| --- | --- | ---: | --- | --- |
| `bc_092g024_4_3_1_xyes_8_utm10_20250826_20250826.laz` | coastal 2025 | 415,068 | EPSG:3157 | CGVD2013 |
| `bc_082n025_4_2_1_xyes_8_utm11_2021.laz` | Golden 2021, steep | 113,775 | EPSG:2955 | CGVD2013 |

Both are LidarBC open point clouds under OGL-BC. The LAZ and bundle bytes stay in
`runtime/` and are not tracked.

## Results

Coastal 2025:

- predicted ground: 374,711;
- low-point flag: 374,787 (90.3% of points);
- SOR removed: 16,526;
- seed points: 44,482;
- iterations: 8;
- HAG p50: 0.0 m;
- HAG p75: 0.0175 m;
- HAG p90: 0.0502 m;
- HAG p95: 24.185 m;
- HAG p99: 42.1668 m;
- HAG max: 59.4299 m;
- runtime: 68.8 s;
- warnings: none.

Golden 2021:

- predicted ground: 82,530;
- low-point flag: 78,965 (69.4% of points);
- SOR removed: 5,355;
- seed points: 3,693;
- iterations: 8;
- HAG p95: 3.5742 m;
- HAG p99: 5.6293 m;
- HAG max: 9.8683 m;
- runtime: 5.8 s;
- warnings: none.

## Bundle validation

Both bundles:

- write `ground.laz`, `manifest.json`, and `qa.json`;
- use `femic.ground-bundle.v1` and `femic.ground-qa.v1`;
- record input/output/QA hashes and the parameter hash;
- record explicit CRS and vertical datum;
- report `ground_truth_used: false`;
- add `is_ground`, `hag`, `is_low`, and `ref_class` dimensions.

The coastal bundle's low-point fraction is 90.3% versus 69.4% on Golden. That is a data
difference: most coastal points sit near the predicted surface, while the Golden tile has a
larger share of high canopy. It is not a defect.

## Interpretation

- The adapter works on a second tile with a different terrain and point distribution.
- The bundle schema and extra dimensions are stable across both tiles.
- The coastal runtime is much longer because it has 3.6 times more points.
- The low-point flag is a downstream segmentation contract, not a ground label.

## Limits

- Two tiles only, both from the same LidarBC program.
- No field or manual point-label validation.
- No CI network job for the real-tile smoke.
- The adapter remains opt-in and does not change FEMIC defaults.
