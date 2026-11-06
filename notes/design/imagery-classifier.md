# Imagery-enhanced conifer/deciduous classifier

Status: active P36 pilot, 2026-11-06. GPU image pilot results are in
`notes/reports/p36-imagery-classifier.md`.

Parent issue: #161

## Why

The P35 structural baseline uses only inventory-derived height and crown width. It reaches
84% accuracy but only ~38% conifer precision because the useful signal is in crown shape,
texture, colour, and local context. A human can separate these crowns in an aerial image;
the model should use the image too.

## Orthophoto sources

- **Vancouver 2022**: public ArcGIS tiled orthophoto service
  `Orthophotos_2022/MapServer` (City of Vancouver). This is real orthophoto imagery, not
  just the tile index. Zoom 19 is ~0.30 m/px.
- **Burnaby 2025**: public `Burnaby_Ortho_2025/MapServer` image export.
- **Surrey 2025**: public orthophoto tile downloader; tiles are large and can be sampled.
- **Coquitlam 2025**: public 7.5 cm MrSID imagery; delivery/large-file handling is pending.

Imagery dates must be recorded against the LiDAR/tree inventory dates.

## Data and labels

- Vancouver public inventory labels are the first training set (184,151 records).
- Surrey public inventory labels are a second available set.
- Burnaby and Coquitlam still have no public species inventory; they cannot provide
  known-good labels. They can be scored with the image model, but their QA remains
  explicitly unlabelled until delivered inventories or manual photo labels exist.
- UBC inventory is an independent campus test if imagery is aligned.

## Pipeline

1. Fetch only tiles/chips intersecting sampled inventory trees and candidates; cache them.
2. Build 96x96 or 128x128 chips at 0.3–0.5 m/px, oversampling conifer to reduce the
   ~89/11 class imbalance.
3. Train a small CNN on GPU (RTX PRO 6000) with spatial block holdout, class-weighted loss,
   augmentation, and early stopping.
4. Fuse image features with LiDAR structural features (height, crown width, CHM shape) in a
   second head or a gradient-boosted stack.
5. Report confusion matrix, balanced accuracy, macro-F1, per-class precision/recall,
   PR-AUC, Brier/calibration, and Wilson/bootstrap intervals.
6. Apply the model to off-inventory candidates in the three P34 instances; keep the P35
   structural baseline for comparison.

## Stereo

The city orthophotos are orthorectified. Overlapping orthophoto tiles do not preserve
usable stereo parallax. True stereo/photogrammetry requires raw overlapping aerial frames
and camera orientation metadata. If those are delivered, generate a photogrammetric DSM
and fuse it with LiDAR; do not call overlapping orthophotos stereo.

## Acceptance

- A GPU-trained image model with a held-out confusion matrix and confidence intervals.
- A direct comparison against the P35 structural baseline.
- Image predictions attached to off-inventory candidates where imagery is available.
- Interface shows model/source/date, image-vs-structural results, and known-good limits.
- Dashboard green and browser smoke clean.
