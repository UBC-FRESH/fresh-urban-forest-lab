# P34 Lower Mainland city instances

Date: 2026-11-06

Status: provisional public-data build; browser verification and dashboard are green.
Parent issue: #149

## What was added

Three independently mounted portal instances:

| Instance | Dataset | Tree table | Buildings | Method label |
| --- | --- | ---: | ---: | --- |
| Surrey | `data/processed/surrey_2025` | 100,940 | 12,005 visual / 137,657 source | public tree inventory; imputed height/DBH |
| Burnaby | `data/processed/burnaby_2022` | 215,811 | 12,038 visual / 54,789 source | 2022 LiDAR CHM candidates |
| Coquitlam | `data/processed/coquitlam_2025` | 287,374 | 12,001 visual / 32,487 source | 20 m LCC canopy candidates |

## Sources

- Surrey Trees, Building Footprints, City Boundary, and 5 m contours (OGL – Surrey).
- Burnaby 2022 0.5 m DEM/DSM, Building Outlines, and Boundary (OGL – Burnaby).
- Coquitlam Buildings, Boundary, and 2023 contours (OGL – Coquitlam).
- Metro Vancouver Land Cover Classification 2020 5 m (OGL – Metro Vancouver).
- OpenStreetMap road centrelines (ODbL 1.0).

Source counts and limits: `notes/p34-sources.md`.

## Methods and limits

- **Surrey:** public tree records are real; the service has no height or DBH, so those
  values are imputed from LCC class and project allometry. Canopy cover uses the Metro LCC
  tree classes, not a Surrey 2022 CHM.
- **Burnaby:** tree records are CHM candidates from the City 2022 DEM/DSM. They are not a
  public-tree census. The CHM is masked by building footprints, LCC buildings, and water;
  crowns above 50 m are rejected as implausible. Conifer/deciduous labels are LCC context.
- **Coquitlam:** tree records are deterministic 20 m canopy candidates from Metro LCC tree
  classes, with class-height assumptions. Canonical Coquitlam LiDAR/imagery is pending.
- All three are screening models. Carbon and rainfall interception use the existing
  allometric/screening methods. No owner names, addresses, or parcel ownership claims are
  included.

## Verification

- Browser smoke on `/surrey/`, `/burnaby/`, and `/coquitlam/`: 2D and 3D loaded with no
  console or page errors; tree counts 100,940 / 215,811 / 287,374.
- `python scripts/dashboard.py`: GREEN, every gate passed.
- Portal `/api/demos`: five slugs.
- Storage root: `/srv/shared-data`; free space after build: 7.7 TB. Processed instances:
  Surrey 329 MB, Burnaby 462 MB, Coquitlam 198 MB.

## What must be re-run after delivery

- Replace Surrey imputed heights with municipal LiDAR/measurements.
- Rebuild Burnaby candidates with the delivered classified point cloud and record
  point-support evidence.
- Replace Coquitlam canopy candidates with the delivered LiDAR/imagery and validate the
  conifer/deciduous classifier with a confusion matrix and confidence intervals.
