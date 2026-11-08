# P46 Surrey-specific 0.30 m image model

Date: 2026-11-08

Status: complete. Inventory validation only; no candidate promotion.

## Result

The Vancouver P36 image CNN was fine-tuned on Surrey 2025 imagery at a 0.30 m chip
footprint and evaluated on a 500 m spatial holdout from the Surrey public-tree inventory.

Spatial holdout: **3,104 rows** (1,517 conifer / 1,587 deciduous).

| Metric | Value | 95% CI |
| --- | ---: | ---: |
| Accuracy | **78.70%** | — |
| Conifer precision | **75.85%** | 73.73–77.85% |
| Conifer recall | **82.79%** | 80.81–84.61% |
| Conifer F1 | 79.17% | — |

The full evaluation JSON is
`data/processed/imagery_classifier/surrey03_report.json`.

## Comparison

| Model | Accuracy | Conifer precision | Conifer recall |
| --- | ---: | ---: | ---: |
| Vancouver transfer at 0.30 m | 72.00% | 78.72% | 58.54% |
| Surrey-specific at 0.30 m | **78.70%** | 75.85% | **82.79%** |
| Surrey-specific at 0.075 m | 81.68% | 82.65% | 80.51% |

Surrey fine-tuning raises accuracy by **6.7 points** and conifer recall by **24.3 points**
relative to the Vancouver transfer. Conifer precision is slightly lower, so the gain is
mostly from detecting more conifers rather than eliminating false positives.

## Limits

- This is inventory-label validation, not candidate validation.
- The candidate-level full-resolution audit remains negative.
- Do not promote candidate scores from this inventory-only result.
- No field validation.
