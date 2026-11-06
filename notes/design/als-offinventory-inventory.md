# ALS off-inventory tree inventory

Status: active P32 plan, 2026-11-05.

Parent issue: #136
Proposed branch: `feature/p32-off-inventory-als`

## Why this phase

The public tree inventory covers boulevards, parks, and other public records. It does not
contain private residential trees. City LiDAR sees that canopy, but a canopy pixel is not a
tree record.

P9 proved the concept on a 500-crown Main Mall pilot. It also showed why a census claim is
not defensible: unmatched crowns can be real off-inventory trees, missed inventory records,
multi-stem clusters, over-segmentation, or shrubs. P32 turns that pilot into a full-city,
confidence-scored candidate inventory that can support private-canopy reporting without
pretending it is an ownership or species inventory.

The target is a **candidate inventory**, not a census.

## Data lock

Implementation lock and checksums: `notes/p32-data-lock.md`. Validation design:
`notes/p32-validation-protocol.md`.

| Need | Source | Use | Licence |
| --- | --- | --- | --- |
| City LiDAR 2022 | City of Vancouver `lidar-2022` (181 tiles) | Vegetation points, height, crown support | OGL – Vancouver |
| City CHM 2022 | P30 `chm.tif` and masks | Segmentation seed and height surface | Derived from OGL – Vancouver |
| Public trees | City of Vancouver `public-trees` (184,151 mapped) | Matching and held-out validation | OGL – Vancouver |
| Property parcels | City of Vancouver `property-parcel-polygons` (99,685) | Parcel context; **not ownership** | OGL – Vancouver |
| Parks | City of Vancouver `parks-polygon-representation` (254) | Public-park context | OGL – Vancouver |
| Roads | OpenStreetMap centrelines | Street/lane context | ODbL 1.0 |
| Orthophoto 2022 | City of Vancouver `orthophoto-imagery-2022` | Manual visual audit | OGL – Vancouver |
| UBC inventory and 2021 CHM | UBC Geodata / UBC 2021 LiDAR | Independent detection and attribute test | PDDL-1.0 / open access |

No owner names, private addresses, private photos, or parcel-level ownership claims are
acquired, stored, or displayed.

## Screening implementation status

The first active build is deliberately narrower than this full method. It uses a 2 m
block-max CHM, tiled local maxima and watershed, a 5 m one-to-one public-tree match, and
parcel/park/zoning/OSM land proxies. Per-crown point support and screening attribute
envelopes are now attached; variable-height windows were tested and rejected because recall
fell. P20 seam merging, multi-peak splitting, the independent UBC test, and independent
human audit remain open P32 tasks. The screening layer is in
`data/processed/vancouver_2022/off_inventory.geojson.gz`; its summary is
`off_inventory.json`.

## Method

### 1. Tiled ALS preparation

- Process the 181 City LAS tiles with a 50–100 m overlap buffer.
- Keep ASPRS classes 3, 4, and 5 (low, medium, high vegetation); use class 2 for ground.
- Normalize vegetation heights with the P30 DEM; preserve the P30 CHM as the primary canopy
  surface.
- Compute per-tile point statistics: count, density, height p50/p95/max, return structure,
  intensity summary, and a deterministic decimated point sample where needed.
- Do not duplicate the 165 GB raw LiDAR corpus; write compact derived tile statistics and
  candidate tables.

### 2. Candidate segmentation

Base detector:

- variable-window local maxima by height class;
- marker-controlled watershed;
- minimum height and crown-area filters;
- P20 non-transitive merge for seam and split-crown cases.

ALS refinement:

- reject segments with no vegetation point support;
- reject building/water/spike segments using P30 masks and point height;
- split segments with multiple distinct vertical peaks;
- carry an evidence score from height, point density, crown shape, and isolation.

The full-city run has no arbitrary 500-candidate cap. Confidence thresholds are explicit and
reported.

### 3. Inventory reconciliation

- Match detected crowns to public trees using one-to-one matching within a stated tolerance.
- Handle multi-stem public records and missed public trees explicitly.
- Keep matched public trees out of the candidate population.
- Report match rate, missed-public count, and unmatched candidate count.

### 4. Public/private land proxy

Overlay candidate locations with:

- parks polygons → `public park`;
- OSM road buffer → `street/lane`;
- property parcels outside parks/streets → `likely private parcel`;
- otherwise → `unknown`.

These are **land-context proxies**, not ownership. The UI must say “likely private parcel,”
never “owned by.”

### 5. Attributes and uncertainty

- height from ALS/CHM, with method and percentile;
- crown width and area from segment geometry and point support;
- DBH from a labelled allometric estimate;
- crown volume and above-ground carbon with species-group priors;
- conifer/deciduous/unknown group only where the vertical profile supports it;
- neighborhood species prior from public trees, never a species assertion;
- confidence for detection, land proxy, and attributes separately.

### 6. Validation

- Hold out public trees by spatial block and evaluate detection recall and precision.
- Use the UBC campus inventory/CHM as an independent test bed for detection and attribute
  error.
- Manual orthophoto audit: fixed random sample of candidates plus matched public trees;
  record tree / not-tree / uncertain and crown boundary quality.
- Report count range under parameter variation, not one false-precision total.
- Compare aggregate candidate area and count with City canopy cover and public inventory.

No claim of field validation.

## App and API

- Generate full-city `off_inventory.json`, `off_inventory.geojson`, and a city summary.
- Add candidate count, high-confidence count, likely-private area, volume, and carbon to the
  City tab.
- Add a confidence/height-styled map layer and a filter.
- Add a clearly labelled 3D candidate overlay or point layer.
- Keep the existing UBC off-inventory layer working.
- Add a public-safe download and privacy notes.

## Compute and storage

- Raw City LiDAR is already 165 GB under `/srv/shared-data`.
- Derived point statistics and candidate tables: budget 10–30 GB.
- Orthophoto: download only audit tiles, not the full 470-tile set.
- Process one LiDAR tile at a time; do not hold the full point cloud in memory.
- Hard stop if shared space drops below 1 TB.

## Tasks

| Task | Issue | Acceptance |
| --- | --- | --- |
| P32.1 Evidence, target, data lock, validation protocol | #137 | Sources, licences, privacy, metrics, sample size fixed |
| P32.2 Full-city ALS point and CHM tiles | #138 | 181 tiles indexed and normalized; QA |
| P32.3 Segmentation and candidate detection | #139 | Full-city candidates; no 500 cap; sensitivity |
| P32.4 Reconciliation and land proxy | #140 | Public matches and likely-private context; no ownership |
| P32.5 Attributes and uncertainty | #141 | Method-labelled height, crown, DBH, carbon, confidence |
| P32.6 City app layer and metrics | #142 | Candidate layer in Vancouver app; browser checks |
| P32.7 Validation, audit, docs, close-out | #143 | Held-out/UBC/orthophoto evidence; report; dashboard |

## Risks

- Over-segmentation of closed residential canopy can inflate counts.
- Suppressed subcanopy trees may be missed by a top-surface CHM.
- Parcel polygons do not identify ownership; “likely private” is only a proxy.
- Orthophoto audit is visual, not a field census.
- Species and DBH are not measured for private candidates.
- Full-city candidate tables and map layers can be large; aggregation and filtering are
  required.

## Activation

P32 is planned. No branch or implementation starts until the maintainer approves activation.
