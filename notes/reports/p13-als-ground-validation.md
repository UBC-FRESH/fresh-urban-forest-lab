# P13.2 validation: PTD-inspired ground classification on a LidarBC tile

Date: 2026-11-04
Phase: P13
Parent issue: #70
Task issue: #80
Status: validation complete; not an operational accuracy claim

## Tile

- Source: LidarBC open point cloud, Open Government Licence - British Columbia.
- File: `bc_092g024_4_3_1_xyes_8_utm10_20250826_20250826.laz`
- URL: https://nrs.objectstore.gov.bc.ca/gdwuts/092/092g/2025/pointcloud/bc_092g024_4_3_1_xyes_8_utm10_20250826_20250826.laz
- Acquisition: 2025-08-26.
- CRS: EPSG:3157 (NAD83(CSRS) / UTM zone 10N).
- Bounds: E 479854.0-E 479998.4, N 5458064.3-N 5458635.9.
- Points: 415,068.
- Classes: 1 = 133,558; 2 = 89,760; 7 = 191,750.
- File size: 2.21 MB. The LAZ stays in `runtime/p13/` and is not tracked.

Class 2 is the published ground class. Class 1 is unclassified, not a negative label.
Class 7 is noise, not a negative label. The tile does not contain an exhaustive ground
truth.

## Method

`classify_ground_ptd` with `cell_size_m=1.0`, `max_iterations=8`, and two settings:

- default: `max_distance_m=2.0`, `max_angle_deg=30.0`;
- strict: `max_distance_m=0.5`, `max_angle_deg=15.0`.

The point-to-triangle-vertex angle gate replaced the initial TIN-facet-slope gate after the
first validation pass. The first pass showed that the facet-slope gate accepted too much
low vegetation and near-ground noise.

## Results

| Setting | Predicted ground | Fraction | Seed points | Iterations | Runtime | Class-2 recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| default | 377,058 | 90.84% | 45,971 | 8 | 65.9 s | 0.999866 |
| strict | 376,587 | 90.73% | 45,971 | 8 | 67.6 s | 0.999822 |

Confusion counts against class 2:

| Setting | TP | FP | FN | TN |
| --- | ---: | ---: | ---: | ---: |
| default | 89,748 | 287,310 | 12 | 37,998 |
| strict | 89,744 | 286,843 | 16 | 38,465 |

The apparent precision against class 2 is about 0.238, but that is **not** a valid accuracy
estimate because class 1 and class 7 are not negatives. It only says that many
non-class-2 points are labelled ground.

Predicted-ground fraction by class at the strict setting:

| Class | Points | Predicted ground | Fraction |
| --- | ---: | ---: | ---: |
| 1 unclassified | 133,558 | 132,883 | 99.49% |
| 2 ground | 89,760 | 89,744 | 99.98% |
| 7 noise | 191,750 | 153,960 | 80.29% |

The class-7 result is the main warning. Many class-7 points are near the ground surface
(75th percentile z about -0.44 m), while a smaller tail is high noise (95th percentile about
40.8 m). The classifier labels the near-ground noise as ground and leaves the high noise
alone. A production pipeline should run SOR or a low-point cut before PTD.

## Height above ground

Strict setting:

| Population | p50 | p75 | p90 | p95 | p99 | max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| all points | 0.0000 | 0.0206 | 0.0855 | 32.2875 | 44.2961 | 61.5205 |
| predicted ground | 0.0000 | 0.0126 | 0.0328 | 0.0475 | 0.0829 | 55.4352 |
| class-2 ground | 0.0000 | 0.0000 | 0.0032 | 0.0094 | 0.0212 | 0.1049 |

Class-2 ground is tight: 99% is within 2.1 cm of the interpolated surface. The whole cloud
separates clearly into a low surface and a high canopy/noise tail.

## Interpretation

- **Supported:** class-2 recall is very high on this tile; the classifier finds essentially
  all published ground points.
- **Not supported:** precision, specificity, or a general accuracy claim. The reference
  classes are incomplete and include noise.
- **Observed weakness:** the classifier over-labels near-ground noise and low vegetation,
  especially class 7. The default is permissive.
- **Do not use operationally yet.** The next step is a low-point cut and SOR pre-pass, then
  a multi-tile validation with a manually checked reference patch.

## Reproduction

From the repository root, with the LAZ in `runtime/p13/`:

```python
from pathlib import Path

import laspy
import numpy as np

from fresh_urban_forest.pointcloud import classify_ground_ptd

path = Path("runtime/p13/bc_092g024_4_3_1_xyes_8_utm10_20250826_20250826.laz")
las = laspy.read(path)
points = np.column_stack([np.asarray(las.x), np.asarray(las.y), np.asarray(las.z)])
result = classify_ground_ptd(
    points,
    cell_size_m=1.0,
    max_angle_deg=15.0,
    max_distance_m=0.5,
    max_iterations=8,
)
```

## Next steps

1. P13.3: add a low-point-cut and SOR pre-pass, then re-run this tile and a second tile.
2. Add a manually checked reference patch or a higher-quality classified tile where class 1
   and class 7 are resolved.
3. Keep the classifier opt-in until the multi-tile evidence exists.
4. Do not move it to FEMIC yet.
