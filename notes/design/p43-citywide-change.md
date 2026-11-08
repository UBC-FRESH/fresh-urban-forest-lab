# P43 citywide observed canopy change 2018–2022

Parent issue: #209
Branch: `feature/p43-citywide-change`
Status: planned

## Goal

Expand the P41 2 km² downtown pilot to the full P30 Vancouver bounds using the full
public 2018 City LiDAR collection.

The product is a repeat-measures LiDAR comparison, not tree survival, growth,
species change, ownership, or causal attribution.

## Data status

- 2018 City LiDAR: 181 ZIP tiles are present under the shared P41/P43 raw tree.
- Total ZIP volume: about 76 GB.
- 2022 later surface: P30 2022 1 m CHM.
- Tile index: `data/raw/tiles/vancouver_2018_city.json`.

## Method

1. Checksum and audit all 181 2018 ZIP tiles.
2. Process each tile to a common **2 m** EPSG:3157 grid:
   - ground surface from class-2 minimum z;
   - canopy surface from class-3/5 maximum z;
   - extract one tile at a time and remove the temporary LAS.
3. Build the 2018 CHM and align it with the P30 2022 CHM at 2 m.
4. Compare at a 2 m canopy threshold: stable, gain, loss, no canopy.
5. Aggregate to the global P38 400 m cells.
6. Join P38 shade/equity, P39 gaps, P40 heat equity, and P42 action labels.
7. Publish JSON, GeoJSON, PNG, API, map toggle, and method note.

## Sampling and uncertainty

- 2018 points may be subsampled per tile for tractability; the sampling stride must be
  recorded and held constant.
- 2 m cells are used because a 5 m maximum aggregation inflated 2018 edge canopy. The 2 m result is still a screen.
- 2018 class-1 unclassified points are excluded from canopy.
- Acquisition date, density, classification, vertical handling, and co-registration
  remain sources of error.
- The product must state the actual valid-overlap area, not the nominal city area.

## Acceptance

- All 181 ZIPs are checksummed or explicitly missing.
- The 2018 CHM covers the P30 bounds with a recorded valid mask.
- 400 m cells report earlier/later canopy, gain, loss, stable, net, and height change.
- Missing or partial coverage is explicit.
- Joins to P38–P42 are descriptive, not causal.
- Dashboard green.
