# Vancouver full-city pilot

Status: active P30 plan, 2026-11-04.

Parent issue: #105
Branch: `feature/p30-vancouver-city`

## Purpose

The UBC demo proves the modelling stack on a small campus. This pilot applies it to the
whole City of Vancouver using only public, downloadable data, so the result can be used by
real planners and tested against real city-scale questions.

The pilot must produce:

- a city-wide 1 m terrain and canopy surface;
- all 184k public trees, with measured/imputed evidence flags;
- city-wide and 22-local-area canopy and ecosystem-service metrics;
- a 3D Vancouver scene that opens from the existing web app;
- reproducible source manifests, processing commands, and stated limits.

It is a screening and decision-support product, not a contractor-grade carbon or
stormwater audit.

## Data lock

| Need | Public source | Snapshot | Licence | Native CRS | Local cache |
| --- | --- | --- | --- | --- | --- |
| City LiDAR 2022 | City of Vancouver `lidar-2022` Open Data | 181 tiles, acquired 2022-09-07/09, ~49 pts/m² | Open Government Licence – Vancouver | EPSG:3157, CGVD28GVRD | `data/raw/city_lidar/2022/` |
| Public trees | City of Vancouver `public-trees` | 184,152 records, modified 2026-11-02 | OGL – Vancouver | EPSG:4326 | `data/raw/vancouver/public_trees.csv` |
| Local areas | City of Vancouver `local-area-boundary` | 22 polygons | OGL – Vancouver | EPSG:4326 | `data/raw/vancouver/local_area_boundary.geojson` |
| Buildings | City of Vancouver `building-footprints-2015` | 154,124 footprints | OGL – Vancouver | EPSG:4326 | `data/raw/vancouver/building_footprints.geojson` |
| Rainfall normals | Environment Canada climate normals, Vancouver Harbour CS | 1981–2010 normal, 1,098.8 mm/yr | Open Government Licence – Canada | n/a | Environment Canada climate normals (recorded in `notes/reports/p30-source-lock.json`) |
| Cross-check LiDAR | Metro Vancouver 2022 classified LAS, 16.5 GB | 2022, QL3, ground/water classes | OGL – Metro Vancouver | EPSG:3157, CGVD28GVRD2018 | optional `data/raw/metro_van_2022/` |

The City LiDAR tile manifest is `data/raw/tiles/vancouver_2022_city.json` and contains all
181 tiles. Source counts, byte sizes, and SHA-256 hashes are in
`notes/reports/p30-source-lock.json`. The webtransfer host blocks plain HTTP clients; use the headed Chromium helper in
`scripts/browser_download_tiles.py` under `xvfb-run`.

The union of the 22 local areas is 118.76 km² in EPSG:3157. LiDAR coverage is larger
(about 134 km²) because it includes UBC Endowment Lands and adjacent area. Metrics are
clipped to the local-area union; the extra LiDAR is retained for context and seam checks.

## Storage budget

Current shared-data free space at plan time: 7.9 TB. All datasets and scratch files go under
`/srv/shared-data/gep/ws4/fresh-urban-forest-lab/data/`; nothing goes on the container root
disk.

| Item | Budget |
| --- | --- |
| Raw 2022 City LiDAR ZIPs (181) | 200 GB |
| Extracted LAS scratch (one to four tiles at a time) | 20 GB |
| 1 m DEM, DSM, CHM, masks, local-area rasters | 10 GB |
| 3D mesh, tree instances, buildings, web payloads | 2 GB |
| Total working budget | 250 GB |

Hard stop: if `/srv/shared-data` drops below 1 TB free, stop acquiring data and finish the
current batch. Delete extracted LAS scratch after each rasterisation. Raw ZIPs are retained
only if the checksummed manifest is complete; otherwise they can be re-fetched.

## Processing design

### AOI and grid

- Reproject the 22 local-area polygons to EPSG:3157.
- Union them into one city AOI polygon; clip all metrics to this polygon.
- Use a 1 m grid aligned to the City LiDAR tile origins. Keep the same origin and
  resolution across DEM, DSM, CHM, and masks.

### Per-tile LiDAR processing

For each 1 km tile:

1. Read the LAS/LAZ header and validate EPSG:3157 and the tile bounds.
2. Ground: class 2 returns; build a 1 m minimum-elevation DEM.
3. Surface: all non-noise returns; build a 1 m maximum-elevation DSM.
4. Canopy: classes 3 and 4 (low and high vegetation) and, where needed, class 1
   non-ground returns; build a 1 m maximum vegetation height above the DEM.
5. Masks: class 5 water, class 6 buildings, class 7 other, class 8 noise.
6. Fill only small DEM gaps with nearest-neighbour interpolation; mark larger gaps as
   nodata. Never fill canopy holes with building heights.
7. Write a tile QA record: point count, class counts, min/max height, nodata fraction.

The LAS uses the ASPRS class scheme even though the portal text lists a different
numbering: 1 unclassified, 2 ground, 3 low vegetation, 4 medium vegetation, 5 high
vegetation, 6 buildings, 7 noise, 9 water. Class counts and spatial patterns confirm that
class 5 is vegetation, not water; class 9 is water. The 1 m CHM is
`max(0, max(class 3,4,5) - DEM)`.

### Mosaic

- Merge tile rasters into one city mosaic.
- Clip to the city AOI.
- Seam check: compare overlapping tile edges; reject or flag seams with a height jump
  greater than 1 m over a 3 m run.
- Output: `dem.tif`, `dsm.tif`, `chm.tif`, `building_mask.tif`, `water_mask.tif`,
  `aoi.geojson`, `manifest.json`.

### Inventory

- Load all 184,152 rows; one row has no coordinate and is counted as unmapped, not dropped.
- Normalise genus/species/cultivar; map species to the existing groups.
- Use the inventory height and DBH where present; use CHM height only as evidence and
  fallback, never silently overwrite a measured value.
- Flag `measured` vs `imputed` for species, DBH, height, and crown width.
- Compare inventory height to the CHM at each tree location by local area; report bias,
  RMSE, and sample counts.
- Reject obvious data-entry outliers from allometric calculations only with an explicit
  flag and count (for example, DBH > 300 cm is flagged for review, not deleted).

### Metrics

City-wide and per local area:

- canopy cover: CHM ≥ 2 m and not building/water, divided by AOI area;
- height distribution: p50, p90, p99, max, and volume-weighted mean;
- canopy volume: `sum(CHM >= 2 m) * 1 m²` (height-field volume) and inventory ellipsoid
  crown volume as a separate estimate;
- carbon storage: existing allometry from DBH/height and species group;
- annual sequestration: existing growth model, reported as a scenario, not a measured flux;
- shade: representative-day shade for 21 June and 21 September, 10:00–16:00, using the
  existing solar/shadow engine with buildings and canopy;
- species diversity: Shannon and Simpson indices, native share, top genera;
- rainfall interception potential: `rainfall * canopy_area * interception_fraction`, using
  the 1,098.8 mm/yr normal, with a stated 10–20% range and a screening label.

Every metric JSON field carries `method`, `evidence_tier`, and `units`. City totals and
local-area totals must reconcile within rounding.

## 3D and web design

- Add a Vancouver city mode alongside the existing UBC demo.
- 2D: MapLibre city boundary, canopy-height raster, public-tree layer, local-area labels.
- 3D: terrain mesh from the DEM at an overview resolution (target 10 m), instanced trees
  from the 184k inventory, simplified building extrusions with heights from LiDAR class 6
  or footprint maxima, and the city boundary.
- Initial camera fits the city; clicking a local area opens its metrics; hovering a tree
  shows species, DBH, height, and evidence flags.
- Keep a compact payload: positions quantised to the city origin, species group as an
  index, height/crown as 16-bit or float32 arrays. Do not ship 184k full JSON objects.
- Target load under 10 s on the lab dev server and interactive frame rate above 20 fps at
  city overview. Measure both.

## Validation and honesty

- Compare inventory height to CHM height: report bias, RMSE, n, and missingness.
- Compare canopy cover to the City's published canopy-cover figures if a compatible public
  figure exists; report the definition mismatch instead of forcing agreement.
- Cross-check a sample of LiDAR canopy heights against Metro Vancouver 2022 or the City
  UBC-core tiles.
- Visual QA: Stanley Park, downtown, a residential area, and the waterfront.
- Do not call carbon or stormwater numbers contractor-grade.
- Do not claim private-land ownership or species for LiDAR-only crowns.

## Tasks and acceptance

| Task | Issue | Acceptance |
| --- | --- | --- |
| P30.1 Source lock, AOI, storage budget, manifest | #106 | 181-tile manifest, 118.76 km² AOI, licence table, free-space guard |
| P30.2 Full-city LiDAR mosaic | #107 | 1 m DEM/DSM/CHM, full AOI, seam/nodata QA |
| P30.3 Full inventory | #108 | 184,152 rows, one unmapped counted, evidence flags, height comparison |
| P30.4 City metrics | #109 | City + 22 local-area metrics with method/evidence fields |
| P30.5 3D city scene | #110 | City mode, fit-to-city, metrics panel, no browser errors |
| P30.6 Validation/docs/close-out | #111 | Dashboard green, docs, screenshots, reproducibility report |

## Verification commands

```bash
python -m fresh_urban_forest.cli tiles vancouver \
  --year 2022 \
  --bbox=-123.2749527,49.1937016,-123.0137253,49.3196669 \
  --out data/raw/tiles/vancouver_2022_city.json

xvfb-run -a python scripts/browser_download_tiles.py \
  --manifest data/raw/tiles/vancouver_2022_city.json \
  --dest data/raw/city_lidar

python scripts/dashboard.py
python scripts/check_workflow.py
```

## Known risks

- The City download host uses a Cloudflare challenge; browser-assisted download is the
  supported path. If it becomes unavailable, fall back to Metro Vancouver 2022 for terrain
  and a City-core sample for vegetation, and state the downgrade.
- The City LiDAR is a single leaf-on snapshot. It cannot support annual growth or
  phenology claims.
- Public trees exclude private trees; LiDAR sees the canopy but not private species or
  ownership.
- Carbon allometry is generic; no local destructive or repeat-measure calibration exists.
- A 184k-tree 3D scene can exceed browser memory if shipped as full objects; the compact
  array payload is a hard requirement.
