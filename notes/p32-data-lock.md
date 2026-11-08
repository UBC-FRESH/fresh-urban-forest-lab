# P32 data lock and screening build

Date: 2026-11-05

Status: P32.1 data lock and validation protocol recorded; P32.3 screening build only.
This is not a P32 close-out. No owner, address, or parcel-level ownership data was
acquired. Validation design: `notes/p32-validation-protocol.md`.

## Source lock

| Source | Local file | Count | SHA-256 prefix | Licence |
| --- | --- | ---: | --- | --- |
| City of Vancouver property parcels | `data/raw/vancouver/property-parcel-polygons.geojson` | 99,685 | `3cd954bb03602e51` | OGL – Vancouver |
| City of Vancouver parks | `data/raw/vancouver/parks-polygon-representation.geojson` | 254 | `f57238b8bad11063` | OGL – Vancouver |
| City of Vancouver 2022 orthophoto index | `data/raw/vancouver/orthophoto-imagery-2022.geojson` | 470 | `2a437e9e18e465c9` | OGL – Vancouver |
| City of Vancouver zoning | `data/raw/vancouver/zoning-districts-and-labels.geojson` | 1,621 | `bb2553c6a5dabba5` | OGL – Vancouver |
| UBC campus tree inventory | `data/raw/vancouver/ubc_campus_trees.geojson` | 9,324 | `c12c5b3dfdf57bc8` | PDDL-1.0 |
| City of Vancouver public trees | `data/raw/vancouver/public_trees.csv` | 184,152 rows | `0c10bff6ea88cf8d` | OGL – Vancouver |
| Enriched city public trees | `data/processed/vancouver_2022/trees.json.gz` | 184,151 | `bb57bfcef7439aef` | Derived from OGL – Vancouver |
| City 2022 CHM | `data/processed/vancouver_2022/chm.tif` | 1 m raster | `81289bd718388d28` | Derived from OGL – Vancouver |
| OSM road centrelines | `data/processed/vancouver_2022/roads.geojson.gz` | 29,318 | `dd074c92f2dd29b0` | ODbL 1.0 |

Retrieved 2026-11-05 from:

- `https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/property-parcel-polygons/exports/geojson`
- `https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/parks-polygon-representation/exports/geojson`
- `https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/orthophoto-imagery-2022/exports/geojson`
- `https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/zoning-districts-and-labels/exports/geojson`
- `https://raw.githubusercontent.com/UBCGeodata/ubc-geospatial-opendata/master/ubcv/landscape/geojson/ubcv_campus_trees.geojson`

The public-tree CSV has one more data row than the enriched accepted records. The build
uses the accepted enriched records; the extra row is not treated as a tree.

## Screening build

Command:

```bash
python scripts/build_vancouver_off_inventory.py
```

The first run detected 528,812 crowns from the 2 m block-max CHM using 1 km tiles with a
40 m buffer and a 5 m local-maxima window. A one-to-one KD-tree match within 5 m matched
130,497 public trees. Building-mask and water-mask centres were excluded, and 336,350
unmatched crowns became candidates.

| Field | Value |
| --- | ---: |
| Detected crowns | 528,812 |
| Matched public trees | 130,497 |
| Unmatched public trees | 53,654 |
| Candidates | 336,350 |
| High confidence (score ≥ 0.6) | 130,103 |
| Summed crown area | 105,047,556 m² |
| Modelled candidate crown volume | 606,472,619 m³ |
| Modelled candidate carbon | 103,421,263 kg |
| Likely private parcel proxy | 163,459 |
| Street/lane proxy | 84,353 |
| Public park proxy | 16,042 |
| Other parcel proxy | 38,121 |
| Unknown proxy | 34,375 |

The land classes are a geographic proxy from parcels, parks, zoning, and OSM roads. They
do not establish ownership.

## Performance and storage

- Full detection: 644 s on the local host, sequential 1 km tiles.
- Candidate build and mask exclusion from the cached detection: 158 s.
- Detection cache: 14 MB compressed; candidate GeoJSON: 11 MB compressed; compact
  high-confidence 3D arrays: 852 KB compressed.
- Orthophoto audit: 300 individual crops plus five contact sheets, about 65 MB, under
  `data/processed/vancouver_2022/off_inventory_audit_sheet/`; source imagery is not
  redistributed in the repository.
- Point support: 336,346 candidate rows, 11 MB compressed; support fields are attached to
  the 336,350-row candidate table. Four southern-edge candidates could not be matched to a
  raw tile.
- The build writes only under `/srv/shared-data`; free space after the build was 7.7 TB.
- The city app serves the compressed candidate layer through
  `/api/off-inventory.geojson` and filters on confidence and land proxy in the browser.

## What this build does not establish

- It is not a census, not an ownership inventory, and not a species inventory.
- It does not yet use per-crown point-cloud support, variable-height windows, P20 seam
  merging, multi-peak splitting, or an orthophoto audit.
- The 5 m one-to-one match is a screening rule, not a field-validated detection
  probability.
- The summed crown area is not a unique canopy area. Crowns can overlap.
- The carbon, volume, and DBH values use the existing allometric screening model with
  unknown species; they are not measurements.
- Held-out public-tree, UBC, and manual orthophoto validation are still open P32 tasks.
