# Detection validation and local allometry: UBC 2021 core campus

Status: first assessment, 2026-11-03.

## Detection validation

Command:

```bash
fresh-urban-forest validate-detection \
  --dataset data/processed/ubc_lidar_2021 \
  --chm data/raw/ubc/lidar_2021/CHM_1m.tif \
  --bbox -123.255,49.255,-123.240,49.268 \
  --out-dir data/processed/validation_2021_core
```

The full 1 m CHM was cropped to the core-campus bbox and downsampled to a 900-pixel
detection grid (about 2 m cells) before local-maxima and watershed segmentation. The
inventory was filtered to the same bbox.

| Metric | Value |
| --- | --- |
| Detected crowns | 12,715 |
| Inventory trees | 4,861 |
| Matched one-to-one | 2,764 |
| Precision | 0.217 |
| Recall | 0.569 |
| F1 | 0.315 |
| Mean match distance | 2.26 m |
| Mean height difference | +1.78 m |
| Height RMSE | 5.04 m |
| Mean crown-radius difference | +0.74 m |

Method: greedy nearest match, highest detected crown first, one inventory tree per
detected crown, 5 m tolerance.

### Tuning

A Main Mall reference patch (`-123.255,49.258,-123.245,49.265`) was swept at 1 m over
minimum heights 3–5 m and windows 3–10 m.

| Min height | Window | Detected | Matched | Precision | Recall | F1 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 3 m | 6 m | 4,004 | 1,268 | 0.317 | 0.434 | **0.366** |
| 3 m | 4 m | 6,816 | 1,742 | 0.256 | 0.597 | 0.358 |
| 3 m | 8 m | 2,717 | 911 | 0.335 | 0.312 | 0.323 |
| 3 m | 10 m | 1,943 | 685 | 0.353 | 0.235 | 0.282 |
| 3 m | 3 m | 16,164 | 2,497 | 0.155 | 0.855 | 0.262 |

Window 6 m gives the best F1 balance. Window 10 m raises precision but loses too much
recall.

The tuned full-core run (`min-height=3`, `window=6`) produced 9,678 detected crowns,
2,314 matches, precision 0.239, recall 0.476, F1 0.318, and a +2.14 m height bias. The
full core is harder than the Main Mall patch, which is why the F1 is lower.

### Interpretation

- The detector **over-segments** the canopy: it returns roughly twice as many crowns as
  there are inventory records in the same area, even after tuning.
- Recall is moderate; a matched crown is usually within 2.3 m of an inventory tree.
- Height bias is +1.78 m and RMSE is 5.04 m. Some of this is the 2 m detection grid, some
  is crown overlap, and some is inventory height error or missing height.
- Precision is not a clean accuracy estimate because the inventory is incomplete,
  especially for remnant forest and dense stands. A detected crown with no inventory
  record may be a real tree that was never measured.
- Next step: create a **complete** field or photo-interpreted reference patch. The current
  inventory is not complete enough to call precision a true error rate.

## Local allometry

Command:

```bash
fresh-urban-forest fit-allometry \
  --dataset data/processed/ubc_lidar_2021 \
  --out data/processed/allometry_ubc.json
```

The fit is `height = 1.3 + coefficient * dbh ** exponent` by species group, using only
trees whose DBH and height are flagged as measured.

| Group | n | Coefficient | Exponent | RMSE | R² | Generic RMSE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Conifer | 1,313 | 0.656 | 0.823 | 7.42 m | 0.342 | 12.38 m |
| Deciduous | 2,762 | 0.695 | 0.745 | 4.87 m | 0.492 | 7.18 m |
| Unknown | 463 | 0.791 | 0.663 | 3.03 m | 0.497 | 7.16 m |

The local fit reduces RMSE against the generic profiles by roughly 30–60 percent on this
inventory. The R² is still modest, which is expected for a mixed urban inventory with
cultivars, pruning, competition, and measurement error.

### Interpretation

- The local fits are an improvement over the generic profiles **as a height prediction**,
  but they are not yet a growth model.
- The conifer sample includes a DBH outlier at 614 cm; outlier filtering and a
  species-level model would improve the fit.
- Annual growth still needs repeat measurements of the same trees. Do not present the
  allometric fit as a growth calibration.
- The fit is written to `data/processed/allometry_ubc.json`; the demo copy is
  `data/demo/ubc_core/allometry.json`.

## Recommendation

1. Keep the generic growth model as the default.
2. Add the local allometry as an optional, clearly labelled predictor.
3. Tune detection at 1 m and validate against a complete reference patch.
4. Collect repeat DBH measurements for a species-level growth calibration.
