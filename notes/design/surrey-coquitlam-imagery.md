# Surrey and Coquitlam imagery classifier

Status: active P37 plan, 2026-11-06.

Parent issue: #168

## Goal

Complete candidate image scoring for Surrey and Coquitlam without pretending the
Vancouver 2022 model transfers cleanly to 2024–25 imagery.

## Data

- Surrey 2025 Metro Vancouver ortho area ZIP, about 12 GB.
- Coquitlam 2025 Metro Vancouver ortho area ZIP, about 11 GB.
- Surrey public tree inventory: 100,940 labelled records.
- Coquitlam has no public species inventory.

## Method

### Surrey

- Extract/convert imagery to a local raster.
- Build labelled chips from Surrey inventory trees.
- Fine-tune or train a Surrey 2025 image CNN with spatial-block validation.
- Apply the selected model to Surrey high-confidence candidates.
- Report confusion matrix, per-class precision/recall, Wilson/bootstrap intervals.

### Coquitlam

- Apply the selected image model to Coquitlam high-confidence candidates.
- Carry source/date/confidence.
- Run a manual orthophoto audit sample, not a known-good inventory QA.
- No confusion-matrix claim without labels.

## Outputs

- `imagery_*` and fusion fields in Surrey/Coquitlam candidate GeoJSON and 3D data.
- UI source/date and coverage labels.
- Model/report artifact with domain-shift caveats.

## Acceptance

- Surrey candidate image scores are produced from 2025 imagery and validated against
  held-out Surrey inventory labels.
- Coquitlam candidate image scores are produced and marked as manual-audit-only.
- No claim that Coquitlam has a known-good confusion matrix.
- Dashboard green; browser smoke clean.
