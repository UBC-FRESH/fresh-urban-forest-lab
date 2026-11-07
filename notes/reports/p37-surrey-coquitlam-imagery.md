# P37 Surrey and Coquitlam imagery candidate scoring

Date: 2026-11-07

Status: image candidate scoring complete; Surrey fine-tune/validation and Coquitlam manual audit remain open.

Parent issue: #168

## Imagery

- Surrey 2025: City of Surrey Aerial Photo April 2025, served through the City
  `AerialImages/MapServer` export endpoint.
- Coquitlam 2025: City of Coquitlam `Imagery_2025_MaxLOD` tiled service.
- Metro 2025 orthophoto source is recorded in `fresh_urban_forest.imagery` for future use.
- Large downloaded SID archives were not usable directly because the local GDAL build has no
  MrSID driver; tile/export services were used instead.

## Results

### Surrey

- 177,361 high-confidence candidates scored.
- Image-only groups: 47,222 conifer / 130,139 deciduous.
- CHM + image fusion groups: 27,831 conifer / 149,530 deciduous.
- Candidate fields: `image_*`, `imagery_*`, `fusion_*`, source/date.
- No known-good candidate-level labels; the public-tree inventory is known-good for training,
  but off-inventory candidates are not.

### Coquitlam

- 85,209 high-confidence candidates scored.
- Image-only transfer model groups: 18,764 conifer / 66,445 deciduous.
- Candidate fields carry source/date/probability.
- Coquitlam has **no public species inventory**. This is not a known-good confusion matrix;
  a manual orthophoto audit is still required before any precision claim.

## Limits

- Surrey applied the Vancouver model plus CHM fusion; no Surrey-specific fine-tune was
  completed in this pass.
- Coquitlam is a transfer application, not a validated Surrey/Coquitlam model.
- Orthophoto dates and tree inventory dates need careful alignment.
- No stereo claim; orthophotos are orthorectified.

## Remaining

- Surrey-specific image model training/validation.
- Coquitlam manual orthophoto audit.
- UI wording and close-out.
