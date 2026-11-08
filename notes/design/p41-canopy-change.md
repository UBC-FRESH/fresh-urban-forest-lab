# P41 observed canopy change 2018–2022

Parent issue: #195
Branch: `feature/p41-canopy-change`
Status: planned

## Goal

Extend the existing observed-change prototype to a city-scale 2018→2022 canopy-change
screen and join the result to the P38 shade, P39 gap, and P40 heat-equity cells.

The output is a **repeat-measures LiDAR comparison**, not a growth rate, survival
estimate, ownership layer, or causal attribution.

## Existing assets

- `fresh_urban_forest.change` already computes stable/gain/loss classes, net area,
  and mean height change on stable canopy.
- `fresh_urban_forest.change_product` writes `change.json`, `change.png`, and
  `change_grid.npz`.
- `data/processed/change_vancouver_2018_2022/` is a 2 km × 1 km downtown product:
  +135,579 m² net canopy, +29.19% gain, −10.59% loss, +0.575 m mean height on stable
  canopy.
- City of Vancouver 2022 LiDAR is processed city-wide in the P30 dataset.
- The 2018 source is the City 2018 LiDAR; the current manifest covers a 26-tile UBC
  subset, so city-wide 2018 acquisition is the first dependency.

## Approved staged AOI

The full 2018 index is 181 tiles and covers 99.96% of the city, but only two tiles
were present. The approved staged pilot is the **2 km² downtown AOI** at
`E492000–E494000, N5456000–N5457000`, using 2018 tiles `4920E_54560N` and
`4930E_54560N`. City-wide acquisition remains a later decision.

## Method

1. Acquire and checksum the 2018 City LiDAR tiles for the P30 city bounds.
2. Build an earlier DEM/CHM on the same EPSG:3157 grid as the later 2022 CHM.
3. Compare aligned canopy-height surfaces at a 2 m canopy threshold:
   - stable canopy
   - gain
   - loss
   - no canopy
4. Report square metres and percent of earlier canopy, plus mean height change on
   stable canopy.
5. Aggregate to 400 m cells and join P38 shade/equity, P39 gap/opportunity, and P40
   LST/heat-equity fields.
6. Publish JSON, GeoJSON, PNG, API endpoints, and a map toggle.

## Required caveats

- 2018 and 2022 differ in acquisition date, season, point density, and vertical datum.
- A canopy-threshold difference is not tree survival, planting, removal, or species change.
- LiDAR elevation/height error and co-registration affect small changes.
- The 2018 full-city tile availability and download path must be verified before claims.
- No causal attribution to policy, ownership, or planting programs.

## Tasks

- P41.1 Acquire and checksum 2018 city LiDAR; verify coverage and metadata.
- P41.2 Build aligned 2018/2022 CHMs on the common grid.
- P41.3 Build 400 m change cells and join P38–P40 fields.
- P41.4 Add API, GeoJSON layer, map toggle, and report.
- P41.5 Dashboard, browser smoke, and close-out.

## Acceptance

- The change product states both acquisition dates, CRS, vertical handling, threshold,
  and overlap.
- Cells report earlier/later canopy, gain, loss, stable, net, and height change.
- The API and map layer are optional when a dataset has no product.
- No ownership, causal, or field-validation claim is made.
- Dashboard is green.
