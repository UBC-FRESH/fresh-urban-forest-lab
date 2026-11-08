# P45 Surrey image-model transfer validation

Date: 2026-11-08

Status: complete. Evaluation only; no candidate promotion.

## Question

Does the Vancouver 2022 0.30 m conifer/deciduous image model transfer to the Surrey public
tree inventory using the already-acquired Surrey 2025 imagery?

## Method

- Surrey public inventory labels: 6,000 conifer and 6,000 deciduous trees.
- 2025 Surrey full-resolution SID imagery, decoded locally and downsampled to a 0.30 m
  chip footprint (96 px; 28.8 m context).
- Vancouver P36 96 px image CNN applied without Surrey fine-tuning.
- 500 m spatial-block holdout; seed `p45-surrey-image-2026-11-08`.
- Train rows: 8,896; test rows: 3,104 (1,517 conifer / 1,587 deciduous).

## Result

| Metric | Value | 95% CI |
| --- | ---: | ---: |
| Accuracy | **72.00%** | 70.40–73.56% |
| Conifer precision | **78.72%** | 76.24–81.01% |
| Conifer recall | **58.54%** | 56.04–60.99% |
| Deciduous precision | **68.17%** | 66.08–70.18% |
| Deciduous recall | **84.88%** | 83.03–86.56% |
| Brier score | 0.2033 | — |

The Vancouver transfer model is biased toward deciduous: it misses **41.5%** of Surrey
inventory conifers.

## Interpretation

A 0.30 m Vancouver model is not a validated Surrey model. Its 72% inventory accuracy and
58.5% conifer recall are materially weaker than the Surrey-specific full-resolution
inventory holdout (81.68% accuracy, 80.51% conifer recall). The full-resolution candidate
audit was still negative (49.1% conifer precision on valid non-black candidates).

This result supports neither candidate promotion nor a claim that the existing Surrey
candidate scores are calibrated.

## Limits

- Inventory labels, not off-inventory candidate labels.
- The model was trained on Vancouver 2022 imagery and applied without Surrey fine-tuning.
- No field validation.
- 0.30 m transfer evaluation is not the same as the 0.075 m Surrey model.
