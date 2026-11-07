# P37 Surrey and Coquitlam full-resolution imagery scoring

Date: 2026-11-07

Status: full-resolution candidate scoring and Surrey spatial validation complete; manual
candidate audit remains open.

Parent issue: #168

## Imagery

- Surrey: City of Surrey Aerial Photo April 2025, 199 MrSID tiles at **0.075 m**.
- Coquitlam: City of Coquitlam Orthophoto 2025, 184 MrSID tiles at **0.075 m**.
- The SID files are decoded through GDAL 3.8.4 with the Hexagon MrSID 10.0.1 decoder,
  installed under `/opt/gdal-mrsid`.
- Each tile was decoded to a tiled, lossless DEFLATE GeoTIFF and indexed by a VRT.
- The scoring path reads native 0.075 m windows; it does not use the City image-service
  renderings that were used for the earlier P36 scores.

## Model

- Surrey public tree inventory labels.
- Balanced sample: 6,000 conifer and 6,000 deciduous trees.
- Chip: **128 x 128 px** at 0.075 m, about **9.6 m** on the ground.
- Spatial block holdout: 500 m.
- Small four-block CNN trained for 10 epochs; best held-out epoch selected.
- Validation rows: 2,904 (1,462 conifer / 1,442 deciduous).

### Held-out Surrey inventory validation

| Metric | Value | 95% interval |
|---|---:|---:|
| Accuracy | 79.13% | 77.62–80.57% |
| Conifer precision | 77.86% | 75.72–79.87% |
| Conifer recall | 81.81% | 79.75–83.70% |
| Deciduous precision | 80.56% | 78.37–82.57% |
| Deciduous recall | 76.42% | 74.16–78.54% |
| Brier score | 0.1514 | — |

This is a Surrey inventory spatial holdout, not a field audit.

## Candidate results

### Surrey

- **177,361** high-confidence candidates scored.
- Full-resolution image-only groups:
  **121,817 conifer / 55,544 deciduous**.
- Source/date/resolution: April 2025, 0.075 m.

### Coquitlam

- **85,209** high-confidence candidates scored.
- Full-resolution image-only transfer groups:
  **46,169 conifer / 39,040 deciduous**.
- Coquitlam has **no public species inventory**. This is not a confusion matrix, and the
  values are not known-good species labels.

## Scale-shift warning

The full-resolution scores are much more conifer-heavy than the P36 0.30 m service scores:

| City | P36 0.30 m image-only | P37 0.075 m image-only |
|---|---:|---:|
| Surrey | 47,222 conifer / 130,139 deciduous | 121,817 / 55,544 |
| Coquitlam | 18,764 / 66,445 | 46,169 / 39,040 |

The full-resolution model has a valid Surrey inventory holdout, but its candidate
distribution shifts sharply. The likely causes include the smaller 9.6 m chip footprint,
local illumination and shadow structure at 7.5 cm, and the fact that off-inventory
candidates are not inventory trees. This shift is **not evidence that the full-resolution
model is more accurate on candidates**. Candidate-level manual audit is required before
using these groups operationally.

## Limits

- Surrey candidate groups have no known-good candidate-level labels.
- Coquitlam is a transfer application; no public species inventory exists.
- No field validation is available.
- Orthophotos are orthorectified; no stereo claim.
- The full-resolution model is image-only. The earlier CHM fusion coefficients were not
  applied because they were fitted to 0.30 m image probabilities.

## Remaining

- Candidate-level manual orthophoto audit, especially the conifer-heavy shift.
- Calibration or model adjustment before operational use.
- Final P37 close-out and merge decision.
