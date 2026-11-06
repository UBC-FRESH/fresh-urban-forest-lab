# P34 source lock

Date: 2026-11-06

Status: source lock and completed provisional builds. Counts are from the downloaded source
layers; output counts are from the completed builds. No owner, address, or parcel-ownership
data is acquired or displayed.

## Source files

| City | Source | Local file | Count / size | Licence |
| --- | --- | --- | --- | --- |
| Surrey | Surrey Trees | `data/raw/lower_mainland/surrey/trees_raw.geojson` | 100,969; 71 MB | OGL – Surrey |
| Surrey | Building Footprints | `data/raw/lower_mainland/surrey/buildings.geojson` | 137,657; 97 MB | OGL – Surrey |
| Surrey | City Boundary | `data/raw/lower_mainland/surrey/boundary.geojson` | 1 polygon | OGL – Surrey |
| Surrey | 5 m contours | `data/raw/lower_mainland/surrey/contours_raw.geojson` | 15,820; 392 MB | OGL – Surrey |
| Burnaby | 2022 0.5 m DEM | `data/raw/lower_mainland/burnaby/Burnaby_0.5m_DEM.zip` | 2.0 GB | OGL – Burnaby |
| Burnaby | 2022 0.5 m DSM | `data/raw/lower_mainland/burnaby/Burnaby_0.5m_DSM.zip` | 2.1 GB | OGL – Burnaby |
| Burnaby | Building Outlines | `data/raw/lower_mainland/burnaby/buildings.geojson` | 54,789; 39 MB | OGL – Burnaby |
| Burnaby | Boundary | `data/raw/lower_mainland/burnaby/boundary.geojson` | 1 polygon | OGL – Burnaby |
| Coquitlam | Buildings | `data/raw/lower_mainland/coquitlam/buildings.geojson` | 32,487; 25 MB | OGL – Coquitlam |
| Coquitlam | City Boundary | `data/raw/lower_mainland/coquitlam/boundary.geojson` | 1 polygon | OGL – Coquitlam |
| Coquitlam | 2023 contours | `data/raw/lower_mainland/coquitlam/contours_raw.geojson` | 4,339; 499 MB | OGL – Coquitlam |
| All | Metro Vancouver LCC 2020 5 m | `data/raw/metro/LCC2020_tif.zip` | 23 MB compressed; 343 MB TIFF | OGL – Metro Vancouver |
| All | OSM road centrelines (main/residential classes) | `data/processed/<city>/roads.geojson.gz` | Surrey 19,073; Burnaby 7,180; Coquitlam 7,320 | ODbL 1.0 |

The city feature services were queried as WGS84 GeoJSON. The Burnaby DEM/DSM are EPSG:3157
and the LCC is EPSG:26910; the build reprojects all layers to EPSG:3157.

## Provisional output counts

| Instance | Dataset directory | Tree records | Buildings | Tree method |
| --- | --- | ---: | ---: | --- |
| Surrey | `data/processed/surrey_2025` | 100,940 | 12,005 visual / 137,657 source | public tree inventory; LCC height imputation |
| Burnaby | `data/processed/burnaby_2022` | 215,811 | 12,038 visual / 54,789 source | DEM/DSM CHM candidates; crowns >50 m rejected |
| Coquitlam | `data/processed/coquitlam_2025` | 287,374 | 12,001 visual / 32,487 source | 20 m LCC canopy-candidate sample |

## Storage and performance

- Surrey build: about 2 minutes; Burnaby CHM candidate build: about 16 minutes; Coquitlam
  canopy build: about 2 minutes on the local host.
- Processed instances: Surrey 329 MB, Burnaby 462 MB, Coquitlam 198 MB.
- Raw Lower Mainland sources: 11 GB; Metro LCC: 46 MB compressed / 343 MB TIFF.
- Free space after the builds: 7.7 TB on `/srv/shared-data`.

## Methods and limits

- Surrey: tree points are public records, but the service has no height or DBH. Heights are
  imputed from Metro LCC tree classes and the project allometry; they are not measured.
- Burnaby: tree records are LiDAR CHM candidates, not a public inventory. Conifer/deciduous
  labels come from Metro LCC classes; they are context, not field species identification.
- Coquitlam: tree records are deterministic 20 m canopy candidates from Metro LCC classes.
  Canonical municipal LiDAR/imagery is pending delivery; this is a placeholder model.
- All: canopy cover and volume describe the compiled raster/class surface. Carbon and
  rainfall interception are screening estimates with the stated method.
- No owner names, addresses, parcel ownership claims, or private photos are stored.
