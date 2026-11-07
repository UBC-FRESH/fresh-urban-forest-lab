# Data licences and attribution

The repository's source code is MIT. Public data keep their own licences. The demo
dataset in `data/demo/ubc_core/` is a derived, downsampled snapshot built to make the
prototype runnable without a multi-gigabyte download. It is **not** a redistribution of
the full source products. Check each publisher's current terms before redistributing or
publishing a new derivative.

| Source | Publisher | Licence or terms | Used for | Notes |
| --- | --- | --- | --- | --- |
| UBC Vancouver campus tree inventory | UBC Campus and Community Planning / UBC Geodata | Public Domain Dedication and License v1.0 (PDDL-1.0) | Tree records, taxa, DBH, height, crown width | Living snapshot; many records are location-only. |
| UBC Vancouver building footprints and legal boundary | UBC Campus and Community Planning / UBC Geodata | PDDL-1.0 | Context, planting constraints | `UBCGeodata/ubc-geospatial-opendata`. |
| UBC Vancouver LiDAR 2021, 1 m CHM, DEM, DSM, and LAZ tiles | UBC Campus and Community Planning / UBC Library Abacus | Open access via the Abacus record; verify the current terms on the dataset page | Terrain, canopy height, raster metrics, point-cloud QA | Acquired 2021-06-23 by Eagle Mapping. DOI-like handle `hdl:11272.1/AB2/Y5KQNB`. |
| City of Vancouver public trees | City of Vancouver | Open Government Licence – Vancouver | Optional street-tree inventory | Refreshed daily on weekdays; filter to the study area. |
| City of Vancouver LiDAR 2013, 2018, 2022 | City of Vancouver | Open Government Licence – Vancouver | Repeat-measures canopy change | 2013 is about 12 points/m²; 2018 about 30; 2022 about 49. |
| City of Vancouver local-area boundary | City of Vancouver | Open Government Licence – Vancouver | City AOI and 22 local-area summaries | 22 polygons; the union is 118.76 km². |
| City of Vancouver building footprints 2015 | City of Vancouver | Open Government Licence – Vancouver | Building mask and 3D context | 154,124 approximate footprints; heights sampled from the 2022 LiDAR. |
| City of Vancouver property parcels | City of Vancouver | Open Government Licence – Vancouver | Land-context proxy for off-inventory candidates | 99,685 polygons; geometry only. No owner or private address is used. |
| City of Vancouver parks | City of Vancouver | Open Government Licence – Vancouver | Public-park land-context proxy | 254 polygons. |
| City of Vancouver zoning districts | City of Vancouver | Open Government Licence – Vancouver | Residential/commercial land-context proxy | 1,621 polygons; a proxy, not an ownership record. |
| City of Vancouver 2022 orthophoto index | City of Vancouver | Open Government Licence – Vancouver | Manual candidate audit | 470 tile footprints; imagery is not redistributed in the repository. |
| City of Vancouver 2022 orthophoto tiles | City of Vancouver | Open Government Licence – Vancouver | GPU image-chip classifier training | Public ArcGIS tiled service; zoom 19 is about 0.30 m/px. |
| City of Burnaby 2025 orthophoto service | City of Burnaby | Open Government Licence – Burnaby | Future image-chip application | Public image service; not yet used in training. |
| City of Surrey 2025 orthophoto tiles | City of Surrey | Open Government Licence – Surrey | Future image-chip application | Public tile downloader; large TIFF tiles. |
| City of Coquitlam 2025 orthophoto | City of Coquitlam | Open Government Licence – Coquitlam | Future image-chip application | 7.5 cm MrSID; delivery/large-file handling pending. |
| City of Surrey public trees | City of Surrey | Open Government Licence – Surrey | Surrey tree instance | 100,969 points; height/DBH are not published in the service. |
| City of Surrey building footprints and contours | City of Surrey | Open Government Licence – Surrey | Surrey building context and provisional terrain | 137,657 footprints; 15,820 5 m contours. |
| City of Burnaby 2022 DEM, DSM, buildings, and boundary | City of Burnaby | Open Government Licence – Burnaby | Burnaby LiDAR candidate instance | 0.5 m DEM/DSM; 54,789 building outlines. |
| City of Coquitlam buildings, boundary, and contours | City of Coquitlam | Open Government Licence – Coquitlam | Coquitlam provisional instance | 32,487 buildings; 2023 contours. |
| Metro Vancouver Land Cover Classification 2020 | Metro Vancouver | Open Government Licence – Metro Vancouver | Conifer/deciduous/shrub context for the three instances | 5 m hybrid land-cover raster; class labels are not species observations. |
| Environment Canada climate normals, Vancouver Harbour CS | Environment and Climate Change Canada | Open Government Licence – Canada | Rainfall-interception screening estimate | 1981–2010 annual precipitation 1,098.8 mm. |
| 2021 Census Profile, dissemination areas | Statistics Canada | Open Government Licence – Canada | Social-equity indicators for the P38 shade screen | Public SDMX Census Profile API; small-area suppression is retained. |
| 2021 Census dissemination-area boundaries | Statistics Canada / public ArcGIS feature service | Statistics Canada terms; verify current terms | Population-weighted areal interpolation | Public feature service; geometry only. |
| Landsat 8/9 Collection 2 Level-2 surface temperature | USGS / NASA, distributed by Microsoft Planetary Computer | Public domain / open data; verify Planetary Computer terms | Land-surface temperature and heat-equity screen | `ST_B10` and `QA_PIXEL`; retrieved for five summer 2022 scenes. |
| OpenStreetMap road centrelines | © OpenStreetMap contributors | Open Database License (ODbL) 1.0 | Pale 2D street underlay and 3D road overlay | Queried from the Overpass API for the demo bbox; attribution is shown in the map HUD. |
| Metro Vancouver classified LiDAR 2022 | Metro Vancouver | Metro Vancouver open-data terms | Regional cross-check | About 16.5 GB for the Vancouver/UBC/UEL area; classified vegetation. |
| LidarBC open LiDAR data | Government of British Columbia / GeoBC | Open Government Licence – British Columbia | Provincial point clouds, DEM/DSM, CHM, and some tree metrics | Tile metadata carries acquisition year, CRS, and quality level. |
| LiDAR Point Clouds – CanElevation Series | Natural Resources Canada | Open Government Licence – Canada | Federal LAZ/COPC point clouds | Distributed by project; projects can overlap. |
| UBC Vancouver LiDAR 2005 and 2015 | UBC Campus and Community Planning / Abacus | Open access via Abacus; verify the current terms | Earlier repeat measures | 2005 covers shoreline areas; 2015 covers the campus. |

## Citation examples

- University of British Columbia. Campus and Community Planning. (2021).
  *University of British Columbia Vancouver Campus Lidar, 2021.* Abacus Data Network.
  https://hdl.handle.net/11272.1/AB2/Y5KQNB
- UBCGeodata. (2024). *UBC geospatial open data.*
  https://github.com/UBCGeodata/ubc-geospatial-opendata
- City of Vancouver. (2022). *LiDAR 2022.* Vancouver Open Data Portal.
  https://opendata.vancouver.ca/explore/dataset/lidar-2022/
- City of Vancouver. *Public trees.* Vancouver Open Data Portal.
  https://opendata.vancouver.ca/explore/dataset/public-trees/
- City of Vancouver. *Property parcel polygons.* Vancouver Open Data Portal.
  https://opendata.vancouver.ca/explore/dataset/property-parcel-polygons/
- City of Vancouver. *Parks polygon representation.* Vancouver Open Data Portal.
  https://opendata.vancouver.ca/explore/dataset/parks-polygon-representation/
- City of Vancouver. *Zoning districts and labels.* Vancouver Open Data Portal.
  https://opendata.vancouver.ca/explore/dataset/zoning-districts-and-labels/
- Statistics Canada. (2023). *Census Profile, 2021 Census of Population.*
  https://www12.statcan.gc.ca/census-recensement/2021/dp-pd/prof/
- Nixon, B., Benson, A., Fillo, M., Shea, E., Caughie, N., & McHale, M. R. (2026).
  *Putting shade where it counts.* Urban Forestry & Urban Greening, 125, 129668.
  https://doi.org/10.1016/j.ufug.2026.129668
- U.S. Geological Survey. *Landsat Collection 2 Level-2.*
  https://www.usgs.gov/landsat-missions/landsat-collection-2-level-2-science-products

## What the demo includes

`data/demo/ubc_core/` contains about 4,900 UBC tree records inside a core-campus
bounding box, a 180-cell terrain grid derived from the 2021 DEM and CHM, the campus
building footprints and boundary, and detected-tree points from the canopy grid. The
source identifiers, licences, and retrieval timestamp are recorded in
`data/demo/ubc_core/manifest.json`.
