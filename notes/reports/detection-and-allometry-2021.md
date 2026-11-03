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

### Interpretation

- The detector **over-segments** the canopy: it returns about 2.6 times as many crowns as
  there are inventory records in the same area.
- Recall is moderate; a matched crown is usually within 2.3 m of an inventory tree.
- Height bias is +1.78 m and RMSE is 5.04 m. Some of this is the 2 m detection grid, some
  is crown overlap, and some is inventory height error or missing height.
- Precision is not a clean accuracy estimate because the inventory is incomplete,
  especially for remnant forest and dense stands. A detected crown with no inventory
  record may be a real tree that was never measured.
- Next step: rerun at 1 m with a tuned window and minimum height, add a field-validation
  sample, and report precision against a **complete** reference patch rather than the
  whole inventory.

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
