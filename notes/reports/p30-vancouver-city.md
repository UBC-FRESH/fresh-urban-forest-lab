# P30 close-out: full Vancouver city canopy pilot

Date: 2026-11-04
Phase: P30
Parent issue: #105
Branch: `feature/p30-vancouver-city`
Pull request: #131
Status: PR queued for maintainer review

## Summary

P30 turns the UBC-core prototype into a full City of Vancouver pilot using only public,
downloadable data. It builds a 1 m city canopy surface from the 2022 City LiDAR, enriches
all 184,151 mapped public trees, computes city and 22-local-area metrics, and adds a City
tab and city-scale 3D scene to the existing app.

No tag, release, Pages setting, repository setting, or public deployment is created by this
phase.

## Evidence

### Source lock

- AOI: 118.76 km² from the union of 22 local-area polygons, EPSG:3157.
- City LiDAR 2022: 181 tiles, 165 GB raw, OGL–Vancouver, EPSG:3157, CGVD28GVRD.
- Public trees: 184,152 rows, 184,151 mapped, OGL–Vancouver.
- Buildings: 154,124 footprints, OGL–Vancouver; 2022 LiDAR heights sampled.
- Climate: Vancouver Harbour CS 1981–2010, 1,098.8 mm/yr, OGL–Canada.
- Hashes and byte counts: `notes/reports/p30-source-lock.json`.

### LiDAR rasterisation

- 181 tiles rasterised at 1 m.
- 8,721,285,369 points.
- Class counts: 1,340,649,172 unclassified; 2,257,627,251 ground; 347,229,158 low
  vegetation; 3,283,090,866 high vegetation; 1,334,773,627 building; 146,360,967 water;
  11,554,328 noise.
- The LAS uses ASPRS classes: 3/4/5 vegetation, 6 building, 9 water. Class 5 is not water
  despite the portal wording.
- Mosaic: 14,670 × 10,771 cells, 1 m, AOI coverage 99.96%, CHM p50 7.46 m, p95 23.75 m.
- Output: `data/processed/vancouver_2022/` (DEM, DSM, CHM, building height/mask, water
  mask, coverage/aoi masks, manifest).

### Inventory

- 184,152 source rows; 184,151 mapped; one row has no coordinate and is counted, not
  dropped.
- 14 DBH outliers above 300 cm are flagged and excluded from allometric carbon/crown
  calculations.
- Species: 1,359 distinct labels; native share 7.61%; median height 7.6 m; p95 22.9 m.
- Completeness: species 99.97%, DBH 99.75%, height 100.00%, crown width 99.75%.
- Inventory-to-CHM height: n=162,497, bias -0.397 m, RMSE 4.292 m, MAE 3.108 m,
  p95 absolute error 8.64 m.
- Full inventory: `trees.json.gz`; summary: `inventory_summary.json`.

### City metrics

- Canopy cover: 26.854% of the 118.76 km² AOI.
- Canopy volume: 350.16 million m³ (height-field volume).
- Inventory crown volume: 49.93 million m³ (ellipsoid estimate).
- Above-ground carbon: 95,792 t.
- Annual sequestration: 1,979 t/yr (one-year growth model).
- Rainfall interception potential: 3.504–7.008 million m³/yr (10–20% screening range).
- Shannon diversity: 5.179.
- Tree shade: 29.29% on the representative June/September sample; combined building plus
  tree shade 43.07%; building shade 22.25%.
- Local-area cover ranges from 47.50% (Shaughnessy) to 9.57% (Strathcona); the full
  22-row table is in the app.
- Published sanity check: City 2025 Urban Forest Strategy reports about 25% canopy cover
  for 2022; this pilot 26.854%, difference +1.854 percentage points. This is a sanity
  check, not calibration.

### Web app

- City pack: 30,000 visual trees (29,096 selected) and 12,000 largest building footprints;
  metrics use all 184,151 trees.
- City tab: 9 KPI cards, 22 local-area rows, method/evidence labels, published-cover
  check, and caveats.
- `/api/city-metrics` serves `city_metrics.json`; `/api/completeness` serves the full
  inventory summary.
- Browser smoke check on the city dataset: no console errors and no page errors after the
  optional-layer flags were added.
- UBC demo smoke check: still loads; the City tab stays hidden.
- Scene payload: about 37 MB. Headless software-WebGL timing: 5.8 s to live and 18.7 s to
  the 3D scene including a 1 s wait. This is a pre-GPU/optimisation number, not a promise.
- Light tab on the city dataset: single instant response about 3.4 s.
- Screenshots: `docs/_static/vancouver-city-metrics.png`,
  `docs/_static/vancouver-city-3d.png`, `docs/_static/vancouver-city-map.png`.

## Tasks

- P30.1 source lock and manifest: complete (#106).
- P30.2 LiDAR mosaic: complete (#107).
- P30.3 inventory and evidence: complete (#108).
- P30.4 city metrics: complete (#109).
- P30.5 City UI and 3D: complete (#110).
- P30.6 validation, docs, close-out: complete (#111).
- P30.7 portal landing page: complete (#132).

## Portal

The two apps share a landing page on the existing FRESH Urban Forest Lab demo port, 8101.
The WS4 portal remains on 8790. The portal mounts `/ubc/` and `/vancouver/`, gives each app
its own runtime directory, and passes a browser smoke check with no console or page errors.
Screenshot: `docs/_static/vancouver-city-portal.png`.

## Limits

- One leaf-on 2022 snapshot; no annual growth or phenology claim.
- Public trees exclude private trees; LiDAR includes private canopy but not species or
  ownership.
- Carbon and sequestration use generic species-group allometry, not local calibration.
- Rainfall interception is a screening range, not a measured flux.
- Shade is a 2.5-D crown/building silhouette sample, not a temperature measurement.
- The 3D scene is a visual sample, not a survey model.
- Building footprints are 2015 approximations; heights are sampled from 2022 LiDAR.

## Verification

```bash
python scripts/dashboard.py
python scripts/check_workflow.py
python scripts/build_vancouver_city.py --jobs 8 --require-complete
python scripts/build_vancouver_inventory.py
python scripts/build_vancouver_metrics.py
python scripts/build_vancouver_pack.py
python scripts/build_vancouver_shade.py
fresh-urban-forest serve --dataset data/processed/vancouver_2022 --port 8000
```

Dashboard: GREEN.

## Approval request

Please review the PR and approve the phase close-out. The merge, parent issue close, and
branch deletion are approval-gated. No release or deployment action is requested.
