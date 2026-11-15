# P68 street-layer UI cue and calibration audit

Parent issue: #326
Branch: `feature/p68-street-audit`
Status: active

## Goal

Make the published street-layer lineage visible in the Vancouver demo and quantify the
largest remaining screening uncertainties without creating a field-validated or
precision/recall product.

## Tasks

1. Add a dynamic count and caveat beside the `street trees` toggle.
2. Audit KartaView FOV metadata and reproject cached detections under 50°, 60°, and 70°
   horizontal-FOV assumptions; report displacement and inventory-match sensitivity.
3. Build a stratified detector contact sheet and document observed missed, merged, and
   implausible detections descriptively.
4. Report inventory-match sensitivity at 4, 6, 8, 10, and 12 m tolerances.
5. Open a PR; do not merge, tag, or release without approval.

## Non-goals

- A new detector or a calibrated camera model.
- Field validation, precision/recall, ownership, survival, or complete-census claims.
- Google Street View imagery.
- Merging street candidates with LiDAR off-inventory or official inventory.
