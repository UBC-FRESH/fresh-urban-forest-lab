# P72 KartaView camera-pose metadata audit

Status: implementation complete; PR #335 open for approval.

## Sample

50 selected street-tree images and their 50 sequences, sampled deterministically from the
P67 image set.

## Photo-level fields

- `cameraParameters`: absent on **50/50** photo records.
- `fieldOfView`: present but **0** on **50/50**.
- `headers`: present on **50/50** (heading).
- `pitch` / `roll`: absent on **50/50**.
- `shotDate` and `sequenceIndex`: present on **50/50**.

## Sequence-level fields

- `cameraParameters`: present on **50/50** sequences.
- Nonzero `hFoV`: **1/50** sequences only (67.256°; corresponding `vFoV` 52.500°).
- **49/50** sequences have all-zero camera parameters and FOV.
- `metadataFileUrl`: present on **50/50**.
- `isVideo`: **1/50** sampled sequences report video.

## Metadata text inspection

The sequence metadata files use `METADATA:2.0` with aliases for `CAMERA`, `EXIF`, `COMPASS`,
`GRAVITY`, and `ATTITUDE`. In the one sampled video file, `CAMERA` and `EXIF` rows expose
hFoV/vFoV and focal length, and compass/gravity rows exist. There is no documented mapping
from the text rows to an individual photo's camera pitch/roll, and the sampled sequence is
the only one with nonzero FOV.

## Conclusion

Direct per-image camera pitch/roll/FOV metadata is **not available at scale** in this sample.
A metadata-driven ground-plane retry is not justified. Any further ground-plane attempt
would need an external calibration method and a representative pitch sample.

No data, canonical layer, or demo change was made.

Artifacts:

- `notes/reports/p72-pose-metadata.json`
- `notes/reports/p72-sequence-fov.json`

## Limits

- 50-image/50-sequence sample, not every sequence.
- No field validation or precision/recall claim.
