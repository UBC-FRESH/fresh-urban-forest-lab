# Data sources for the UBC and Metro Vancouver pilot

Status: reference note, 2026-11-03.

This note records what is publicly available, what we actually used, what each source can
and cannot support, and the traps that would make a change analysis wrong.

## Summary

| Need | Best available source | Coverage | Native CRS | Why it matters |
| --- | --- | --- | --- | --- |
| Campus tree records | UBC Geodata `ubcv_campus_trees` | UBC Vancouver campus, about 9,300 points | EPSG:4326 | Species, DBH, height, crown width where measured; many location-only records. |
| Campus terrain and canopy | UBC 2021 LiDAR CHM/DEM/DSM 1 m | UBC campus plus Pacific Spirit Park and Musqueam Reserve No. 2 | EPSG:3157 | The strongest single-date structural baseline. |
| Campus point cloud | UBC 2021 LAZ tiles | 1 km tiles; full coverage is hundreds of MB per tile | EPSG:3157 | Needed for true point-cloud metrics and future segmentation. |
| Repeat campus LiDAR | UBC 2005, 2010 (cliffs/bare earth), 2015, 2021 | Partial to full campus | EPSG:3157 / legacy | Repeat measures for growth and loss. |
| City-wide repeat LiDAR | City of Vancouver 2013, 2018, 2022 | City jurisdiction and UBC Endowment Lands | EPSG:3157 | The best three-date citywide change series. |
| Regional classified LiDAR | Metro Vancouver 2022 | Vancouver, UBC, UEL, Electoral Area A | EPSG:3157 | Classified vegetation classes; about 16.5 GB. |
| Street-tree inventory | City of Vancouver `public-trees` | Public boulevards and parks | EPSG:4326 | About 180,000 records; daily refresh. |
| Buildings and boundary | UBC Geodata buildings and legal boundary | UBC campus | EPSG:4326 | Context, planting constraints, 3D massing. |

## UBC tree inventory

- Source: `UBCGeodata/ubc-geospatial-opendata`, `ubcv/landscape/geojson/ubcv_campus_trees.geojson`
  and the matching CSV.
- Licence: PDDL-1.0.
- Records: 9,324 points in the snapshot used here. About 4,600 have height, 4,600 have
  DBH, and 4,650 have crown width. 566 taxa strings and 480 common names.
- Fields: `TREEID`, `TAXA`, `COMMON_NAME`, `DBH`, `THEIGHT`, `CROWNWIDTH1`,
  `CROWNWIDTH2`, `CROWN_LIGHTEXP`, `TREE_TYPE`, `NATIVE_TREE`, `TREE_STATUS`,
  `DATE_MEASURE`, and location.
- Traps:
  - many records are location-only, so any species or size summary must report a
    completeness rate;
  - taxa strings are not a controlled vocabulary (misspellings, cultivars, `spp.`);
  - height may have been derived from an earlier LiDAR surface, so it is not independent
    of the CHM;
  - the inventory is a living snapshot, not a fixed annual release.

## UBC 2021 LiDAR

- Source record: `hdl:11272.1/AB2/Y5KQNB`.
- Acquisition: 2021-06-23 by Eagle Mapping, for UBC Campus and Community Planning.
- Products: LAZ tiles, 1 m CHM, 1 m DEM, 1 m DSM, 50 cm rasters, contours, hillshades,
  and a report.
- CRS: EPSG:3157, NAD83(CSRS) UTM 10N, vertical datum CGVD28GVRD (the file headers and
  the Abacus metadata should be checked together).
- Accuracy: about ±0.30 m horizontal and ±0.15 m vertical according to the producer.
- Trap: the 1 m DEM is 5,790 columns wide and the CHM is 5,789 wide. They share an origin
  but not an exact width. The loader trims to the common upper-left window and records
  that it did so.

## City of Vancouver LiDAR

- 2013: at least 12 points/m², acquired 2013-02-07, 15, and 19; LAS and GeoTIFF tiles.
- 2018: about 30 points/m², acquired 2018-08-27 and 28.
- 2022: about 49 points/m², acquired 2022-09-07 and 09; 181 tiled LAS downloads; 134 km².
- CRS: EPSG:3157; vertical datum CGVD28GVRD.
- Trap: acquisition dates are not leaf-on/leaf-off consistent. The 2013 flight is
  winter; 2018 and 2022 are late summer. A raw CHM difference will confound phenology,
  shadow, and canopy motion with real change.
- Trap: the city layer covers the City of Vancouver and UBC Endowment Lands, not all of
  the UBC campus. Use the UBC 2021 product for campus and the city product for the
  surrounding street grid.

## Metro Vancouver 2022

- Classified LAS, about 16.5 GB for the Vancouver/UBC/UEL area.
- Quality Level 3, EPSG:3157, CGVD28GVRD2018.
- Strong cross-check for the City product because vegetation is explicitly classified.
- Trap: large download; plan a tile-level catalog and a local cache, not a single fetch.

## City of Vancouver public trees

- Source: `opendata.vancouver.ca`, dataset `public-trees`.
- Licence: Open Government Licence – Vancouver.
- Fields: `asset_id`, address, common/genus/species/cultivar, height in metres, diameter
  in centimetres, local area, point geometry.
- Trap: records without coordinates are omitted from the mapped view; the export can be
  stale for individual attributes; park and private trees are not included.

## Coordinate and vertical datums

- Use EPSG:3157 for metric work. Do not mix EPSG:26910 and EPSG:3157 silently; they are
  close but not identical.
- Keep the vertical datum in the manifest. A CHM difference between two datums can look
  like a uniform height shift.
- The browser payload carries both WGS84 coordinates for MapLibre and local metres for
  Three.js, with one explicit origin.

## Recommended pilot sequence

1. Use UBC 2021 CHM/DEM/DSM + UBC tree inventory for the baseline.
2. Add UBC 2015 or 2005 LiDAR for a campus repeat-measures test.
3. Add City 2018 and 2022 LiDAR for the surrounding street grid and a three-date change
   series.
4. Add Metro Vancouver 2022 classified LiDAR as an independent structural cross-check.
5. Only then fit local growth curves from repeat measurements; do not treat a generic
   allometry as a calibrated Vancouver growth model.

## What the prototype actually uses

`data/demo/ubc_core/` is built from the UBC 2021 CHM/DEM, the UBC tree inventory, the UBC
buildings and boundary, and a core-campus bounding box. The full processed dataset is in
`data/processed/ubc_lidar_2021/` locally but is gitignored because it is derived from
large source rasters. The manifest records every source and its licence.
