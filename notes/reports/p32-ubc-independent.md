# P32 independent UBC test

Date: 2026-11-06

Status: independent detection and attribute test complete. This is not a precision test
because the UBC inventory is incomplete.

## Inputs and frozen method

- UBC 2021 CHM, 1 m, EPSG:3157: `data/raw/ubc/lidar_2021/CHM_1m.tif`.
- UBC campus tree inventory: 9,324 source records.
- Detector: frozen City settings — 2 m block-max CHM, 1 km tiles, 40 m buffer, 5 m
  local-maxima window, 3 m minimum height, watershed centroids.
- One-to-one matching within 5 m.
- No UBC tuning.

Eligible UBC records were live, not marked removed, not hedges, and inside the CHM frame:
**9,138**.

## Detection result

| Metric | Value |
| --- | ---: |
| UBC eligible records | 9,138 |
| Detected crowns | 129,578 |
| One-to-one matches within 5 m | 4,810 |
| Recall | **52.64%** |
| Missed nearest distance p50 | 5.32 m |
| Missed nearest distance p95 | 9.81 m |

This is substantially lower than the City held-out public-tree recall of 76.6%. The UBC
campus inventory is denser and includes many small or understory records, and the frozen
City detector was not tuned for it. The result is evidence that the candidate layer is not
uniformly complete across land types.

The 129,578 detected crowns cannot be converted to precision against a 9,138-record
inventory that is known to be incomplete.

## Attribute residuals on matched measured records

| Attribute | n | Bias | MAE | RMSE | p5 | p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Height (m) | 2,447 | +2.03 | 3.46 | 6.65 | −3.46 | +12.11 |
| Crown width (m) | 2,455 | +1.26 | 4.51 | 6.67 | −8.42 | +10.67 |
| DBH (cm) | 2,444 | −9.45 | 19.32 | 27.28 | −46.59 | +32.74 |

DBH uses the City unknown-species height-to-DBH allometry; it is not a UBC-calibrated
model. Height and crown residuals mix segmentation, matching, inventory measurement, and
species differences.

## Conclusion

UBC is an independent test, and it does **not** support a high uniform recall claim. The
City result and the UBC result should both be reported. P32 remains a screening candidate
inventory, not a validated census. No parameter tuning was performed on UBC.

Report JSON: `data/processed/vancouver_2022/off_inventory_ubc_validation.json`.
