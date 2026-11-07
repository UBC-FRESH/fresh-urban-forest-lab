# Surrey and Coquitlam imagery classifier

Status: active P37, full-resolution scoring complete 2026-11-07; candidate audit open.

Parent issue: #168

## Goal

Complete candidate image scoring for Surrey and Coquitlam without pretending the
Vancouver 2022 model transfers cleanly to 2024–25 imagery.

## Data

- Surrey 2025 Metro Vancouver ortho area ZIP, about 12 GB.
- Coquitlam 2025 Metro Vancouver ortho area ZIP, about 11 GB.
- Surrey public tree inventory: 100,940 labelled records.
- Coquitlam has no public species inventory.
- The downloaded SID archives are valid MrSID. A local GDAL 3.8.4 + Hexagon MrSID 10.0.1
  build is installed under `/opt/gdal-mrsid`, so `gdalinfo`/`gdal_translate` can read them.

## Method

### Surrey

- Decode the 199 Surrey SID tiles to tiled DEFLATE GeoTIFFs and index them with a VRT.
- Build labelled 128 px chips at native 0.075 m from Surrey inventory trees.
- Train a Surrey 2025 image CNN with 500 m spatial-block validation.
- Apply the selected 128 px model to Surrey high-confidence candidates.
- Report confusion matrix, per-class precision/recall, Wilson/bootstrap intervals.
- Compare the full-resolution candidate distribution with the P36 0.30 m service scores;
  an unexplained scale shift must be treated as a model-audit issue, not an improvement.

### Coquitlam

- Decode the 184 Coquitlam SID tiles to the same VRT/GeoTIFF form.
- Apply the selected Surrey full-resolution image model to Coquitlam candidates.
- Carry source/date/resolution/confidence.
- Run a manual orthophoto audit sample, not a known-good inventory QA.
- No confusion-matrix claim without labels.

## Outputs

- Full-resolution `image_*`/`imagery_*` fields in Surrey/Coquitlam candidate GeoJSON and 3D data.
- UI source/date/resolution and coverage labels.
- Model/report artifact with domain-shift caveats.

## Acceptance

- Surrey candidate image scores are produced from 2025 imagery and validated against
  held-out Surrey inventory labels.
- Coquitlam candidate image scores are produced and marked as manual-audit-only.
- No claim that Coquitlam has a known-good confusion matrix.
- Dashboard green; browser smoke clean.
