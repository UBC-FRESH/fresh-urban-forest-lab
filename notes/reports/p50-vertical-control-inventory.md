# P50.1 vertical-reference inventory and feasibility gate

Status: feasibility gate reached. P50.2 is blocked pending access to 2018 raw tiles or an
independent external control. P45's warning remains in force.

## Purpose

Inventory the data needed to estimate a vertical offset between the 2018 and 2022 LiDAR
surfaces without using canopy as a control. This is an inventory and access report, not an
offset estimate.

## Local inputs

### 2018 source

- City of Vancouver LiDAR 2018, 181 indexed ZIP tiles.
- Total indexed size: **78.04 GB**.
- Index: `data/raw/tiles/vancouver_2018_city.json`.
- Source projection: UTM Zone 10, NAD83(CSRS); vertical datum CGVD28GVRD.
- Classes of interest: class 2 bare earth/low grass, class 6 buildings.
- **Raw ZIPs are not present locally.** Only the tile index and checksum/missing-tile
  metadata are local.
- A test `curl` request to the first indexed tile URL on 2026-11-08 returned **HTTP 403**.
  The City source note already warns that `webtransfer.vancouver.ca` may block automated
  clients. This is an access blocker, not evidence that the files are unavailable to a
  browser/manual user.

### 2022 source

Local P30 files under `data/processed/vancouver_2022/`:

| File | Grid | CRS | Approx. size |
| --- | --- | --- | ---: |
| `dem.tif` | 14,670 × 10,771, 1 m | EPSG:3157 | 227 MB |
| `dsm.tif` | 14,670 × 10,771, 1 m | EPSG:3157 | 318 MB |
| `chm.tif` | 14,670 × 10,771, 1 m | EPSG:3157 | 134 MB |
| `building_mask.tif` | 14,670 × 10,771, 1 m | EPSG:3157 | 3.6 MB |
| `roads.geojson.gz` | vector | EPSG:3157 | 1.2 MB |

Vertical datum: CGVD28GVRD per the dataset source notes. The 2022 acquisition is
September 2022; the City page reports 0.081 m vertical accuracy at 95% confidence.

### Existing change products

- P43 5 m earlier/later CHMs and 2 m change product.
- P43 `change_process.json`: 181 tiles, 6.44 billion input points, 100.7 million sampled
  points, 5 m resolution, stride 64.
- P45 sensitivity: net −99 ha to +488 ha across ±1 m; 2 m release remains preferred.
- P45 explicitly requires external vertical control.

## Stable control candidates

If 2018 raw tiles become available:

1. **Bare-earth ground, class 2** paired with the 2022 DEM.
2. **Building roofs, class 6** paired with the 2022 DSM, restricted to stable footprints.
3. **Road/infrastructure surfaces** paired with the 2022 DSM/DEM, excluding resurfacing
   and construction areas.
4. **External independent references** if accessible: ICESat-2 ATL03/ATL08, GEDI L2A, or
   provincial/geodetic benchmarks.

Canopy, vegetation classes, and tree points are excluded as controls.

## Feasibility gate

| Question | Result |
| --- | --- |
| 2018 raw LAS local? | **No** |
| 2018 raw reproducible through automated access? | **No; HTTP 403 on the indexed URL** |
| Stable non-canopy control candidates? | Yes, if 2018 raw is obtained |
| Independent external vertical reference local? | **No; access/licence not confirmed** |
| Enough paired observations possible? | Cannot determine until a raw sample is obtained |

## Decision

**No-go for automatic P50.2 at this time.** The phase should stop before estimation rather
than substitute canopy, model, or unverified external data for control.

P50 remains deferred until one of these is provided:

- a manual/browser download of a small, spatially distributed 2018 tile sample; or
- an approved alternate 2018 raw-data endpoint; or
- an accessible independent vertical reference with documented licence and lineage.

The existing P43/P45 result stands only as a turnover screen. Do not claim a citywide net
gain or loss without vertical control.

## Suggested sample if data are provided

Use 6–12 tiles distributed across the city, including:
- flat downtown/False Creek surfaces;
- residential areas with stable building roofs;
- at least one area with recent construction flagged as a QA exclusion.

Report sample counts, spatial coverage, robust offset, outliers, and bootstrap uncertainty.
Do not extrapolate to the city without a representativeness check.
