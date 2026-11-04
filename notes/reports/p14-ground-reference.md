# P14 ground reference and second terrain validation

Date: 2026-11-04
Phase: P14
Parent issue: #89
Tasks: #90, #91, #92
Status: validation complete; FEMIC adapter approved as an optional prototype only

## Reference construction

The reference does **not** use the classifier's own HAG. It uses the published class 2 as
the positive ground set and builds a class-2 reference surface:

1. Positive ground: `classification == 2`.
2. Reference surface: the nearest published class-2 point in XY, with reference HAG equal
   to `z - nearest_class_2_z`.
3. High-confidence non-ground: non-class-2 points with reference HAG > 2 m.
4. Ambiguous band: non-class-2 points with reference HAG between 0 and 2 m. These are
   excluded from the negative set.

This is reproducible and independent of the classifier, but it is not a manually labelled
point cloud. The ambiguous band is large, especially on the coastal tile, because class 1 is
unclassified and class 7 is noise.

## Tiles

| Tile | Setting | Points | Class counts | Relief | CRS |
| --- | --- | ---: | --- | ---: | --- |
| `bc_092g024_4_3_1_xyes_8_utm10_20250826_20250826.laz` | coastal 2025 | 415,068 | 1: 133,558; 2: 89,760; 7: 191,750 | about 64 m | EPSG:3157 |
| `bc_082n025_4_2_1_xyes_8_utm11_2021.laz` | Golden-area 2021, steep | 113,775 | 1: 98,182; 2: 15,353; 7: 240 | about 62 m | EPSG:2955 + CGVD2013 |

Both are LidarBC open point clouds under OGL-BC. The LAZ files stay in `runtime/` and are
not tracked.

## Method

P13 policy:

1. `statistical_outlier_mask(k=10, multiplier=2.0)`;
2. `classify_ground_ptd(cell_size_m=1.0, max_angle_deg=15.0, max_distance_m=0.5, max_iterations=8)`;
3. `low_point_mask(height_above_ground, cut_m=0.15)` for downstream use.

## Results

| Metric | Coastal 2025 | Steep 2021 |
| --- | ---: | ---: |
| Points | 415,068 | 113,775 |
| High-confidence non-ground (reference HAG > 2 m) | 39,228 | 17,900 |
| Ambiguous 0-2 m band | 286,080 | 80,522 |
| SOR removed | 16,526 (3.98%) | 5,355 (4.71%) |
| Predicted ground | 374,711 (94.02% of kept) | 82,530 (76.12% of kept) |
| Class-2 recall | 0.999866 | 0.963423 |
| High-confidence false-ground | 812 / 24,258 | 666 / 14,313 |
| High-confidence false-ground rate | 3.35% | 4.65% |
| Class-2 HAG p95 | 0.0094 m | 0.0010 m |
| Class-2 HAG p99 | 0.0217 m | 0.0441 m |
| Low-point flag on false ground | 71.4% | 67.0% |
| Runtime, SOR + PTD | 62.0 s | 4.9 s |

## Interpretation

- The classifier transfers to the steep interior tile. Class-2 recall is lower (96.3% vs
  99.99%) but still high for a simplified method.
- The high-confidence false-ground rate is 3.3-4.7% on both tiles. That is a real error
  rate, not a precision estimate against an exhaustive truth.
- Class-2 HAG remains tight: p99 is 2.2 cm coastal and 4.4 cm steep.
- The low-point flag catches about two-thirds of the high-confidence false ground because
  those points sit close to the PTD surface. It is a downstream guard, not a correction.
- The ambiguous 0-2 m band is large. No claim is made about those points.

## P14.3 FEMIC decision

**Decision: approve an optional FEMIC adapter prototype, not a default pipeline change.**

The evidence supports a prototype because:

- class-2 recall is high on both terrain types;
- high-confidence false-ground is low and measured;
- HAG is tight;
- the low-point policy is explicit;
- the classifier is still opt-in and does not change existing products.

Conditions before any operational use or default FEMIC path:

1. A manually labelled reference patch, not only the class-2 nearest-surface reference.
2. A FEMIC-side design that keeps the adapter optional and versioned.
3. A stable contract for `GroundClassification`, `low_point_mask`, SOR parameters, and
   provenance.
4. A second steep tile and a second coastal tile to show the result is not tile-specific.
5. A clear statement that class 1 and class 7 remain unresolved in the reference.

## Limits

- The reference is reproducible but not manually labelled.
- The ambiguous 0-2 m band is excluded, so the false-ground rate is not a full error rate.
- The steep tile is small (113,775 points) and from one map sheet.
- The classifier remains a simplified PTD-inspired implementation.
- No production FEMIC integration is included.
