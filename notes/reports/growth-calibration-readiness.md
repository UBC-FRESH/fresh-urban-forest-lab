# Growth calibration readiness: UBC inventory

Status: data-gap assessment, 2026-11-03.

## What we checked

The UBC campus inventory has 9,324 records and 9,322 distinct tree IDs. Of those, **zero**
tree IDs have more than one measurement date. There are 4,568 trees with both DBH and
height flagged as measured, but those are **cross-sectional**, not repeated measurements
of the same tree.

The date field is populated for roughly half the records, but the values cluster by
cohort and survey round, not by tree. A tree is measured once, not revisited.

## Consequence

We cannot fit an annual DBH increment or a local growth curve from this inventory. The
local allometry in `notes/reports/detection-and-allometry-2021.md` is a height-diameter
fit, not a growth model. The generic growth model remains the only scenario engine.

## What would make growth calibration possible

1. **Repeat the UBC inventory** and keep a stable `tree_id` across rounds. The UFOR 220
   multi-year phases already provide the field structure; the missing piece is a
   re-measurement round on the same trees.
2. **Permanent sample plots** on campus, stratified by species group, land use, and
   growing space. Ten to twenty plots with 20–50 trees each would be enough for a first
   local increment model.
3. **Use repeat LiDAR for crown expansion** and pair it with a smaller field sample for
   DBH. LiDAR cannot measure DBH directly, but it can constrain crown growth and height
   change.
4. **Keep the generic model as a prior** and compare it with `fresh-fvsbc` and the Urban
   Tree Database for native conifers; do not present the generic model as calibrated.

## Data contract request

- Keep `tree_id` stable across measurement rounds.
- Add `measurement_id` and `measurement_date` to every record.
- Record `dbh_cm`, `height_m`, `crown_width_m`, `crown_base_height_m`, `condition`, and
  `crown_light_exposure` on every round.
- Preserve the original measured values alongside any imputed value.
- Record the survey method and crew so method changes are visible.

## Status

Growth calibration is **blocked by data**, not by code. The code path is ready to fit the
model once repeat measurements exist.
