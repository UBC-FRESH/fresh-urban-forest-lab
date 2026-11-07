# P37 Surrey and Coquitlam full-resolution imagery scoring

Date: 2026-11-07

Status: corrected full-resolution scoring complete; 200-candidate audit packet ready for
human review.

Parent issue: #168

## Imagery

- Surrey: City of Surrey Aerial Photo April 2025, 199 MrSID tiles at **0.075 m**.
- Coquitlam: City of Coquitlam Orthophoto 2025, 184 MrSID tiles at **0.075 m**.
- The SID files are decoded through GDAL 3.8.4 with the Hexagon MrSID 10.0.1 decoder,
  installed under `/opt/gdal-mrsid`.
- Each tile was decoded to a tiled, lossless DEFLATE GeoTIFF and indexed by a VRT.
- Scoring reads native 0.075 m windows; it does not use the City image-service renderings
  used for the earlier P36 scores.

## Correction

The first full-resolution run incorrectly treated GDAL `ReadRaster` output as RGB
pixel-interleaved data; this GDAL build returns band-sequential bytes for a three-band
read. The channel order was corrected in `fresh_urban_forest.fullres_imagery`.

The earlier full-resolution figures (79.13% validation, 121,817 Surrey conifer, 46,169
Coquitlam conifer) are therefore **superseded and invalid**. The corrected results below
are the ones to use.

## Model

- Surrey public tree inventory labels.
- Balanced sample: 6,000 conifer and 6,000 deciduous trees.
- Chip: **128 x 128 px** at 0.075 m, about **9.6 m** on the ground.
- Spatial block holdout: 500 m.
- Small four-block CNN trained for 10 epochs; best held-out epoch selected.
- Validation rows: 2,904 (1,462 conifer / 1,442 deciduous).
- A 192 px / 14.4 m trial scored 77.51% accuracy and was rejected.

### Held-out Surrey inventory validation

| Metric | Value | 95% interval |
|---|---:|---:|
| Accuracy | 81.68% | 80.23–83.05% |
| Conifer precision | 82.65% | 80.60–84.53% |
| Conifer recall | 80.51% | 78.40–82.46% |
| Deciduous precision | 80.74% | 78.66–82.67% |
| Deciduous recall | 82.87% | 80.84–84.73% |
| Brier score | 0.1462 | — |

This is a Surrey inventory spatial holdout, not a field audit.

## Candidate results

### Surrey

- **177,361** high-confidence candidates scored.
- Full-resolution image-only groups:
  **104,255 conifer / 73,106 deciduous**.
- Source/date/resolution: April 2025, 0.075 m.

### Coquitlam

- **85,209** high-confidence candidates scored.
- Full-resolution image-only transfer groups:
  **43,111 conifer / 42,098 deciduous**.
- Coquitlam has **no public species inventory**. This is not a confusion matrix, and the
  values are not known-good species labels.

## Scale comparison

A 1,000-candidate stratified sample was scored on the same points with:

- the P37 0.075 m model on its native 9.6 m chip; and
- the P36 0.30 m model on a 96 px bilinear downsample of the same 28.8 m crop.

The comparison uses the same raw SID imagery, not the City image service.

| Measure | Result |
|---|---:|
| Full-resolution conifer share | 50.0% |
| 0.30 m conifer share | 56.4% |
| Agreement at 0.5 | 73.2% |
| Probability correlation | 0.457 |
| Mean probability difference | −0.032 |
| Saved vs recomputed full-resolution MAD | 0.000024 |

The corrected models are broadly comparable in aggregate. They still disagree on a
meaningful minority of points, so candidate-level audit is required.

## Audit packet

The review uses the existing P32 blind, offline human-verification UI pattern rather than
a separate review protocol.

Directory: `data/processed/surrey_2025/fullres_verification_packet/`

- `index.html`: blind 200-candidate review UI with Conifer / Deciduous / Uncertain
  buttons, notes, progress, filters, local-storage autosave, CSV import/export, and a
  print stylesheet.
- `images/`: 200 full-resolution 28.8 m crops with a red centre crosshair.
- `review_template.csv`: blank candidate IDs and labels.
- `candidate_metadata.csv`: model probabilities and source indices; not for use during
  the first blind pass.
- `README.md`: reviewer instructions.
- `fullres_verification_packet.zip`: distributable packet.

The same-point comparison records remain in `data/processed/surrey_2025/fullres_audit/`.

No human labels have been entered. The packet is ready for review; no candidate-level
precision claim is made yet.

## Limits

- Surrey candidate groups have no known-good candidate-level labels.
- Coquitlam is a transfer application; no public species inventory exists.
- No field validation is available.
- Orthophotos are orthorectified; no stereo claim.
- The full-resolution model is image-only. The earlier CHM fusion coefficients were not
  applied because they were fitted to 0.30 m image probabilities.

## Remaining

- Human review of the 200-candidate audit packet.
- Candidate-level precision summary and decision on merge/retrain.
- Final P37 close-out.
