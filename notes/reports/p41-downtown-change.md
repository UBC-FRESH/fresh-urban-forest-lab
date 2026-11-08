# P41 downtown 2018→2022 canopy change pilot

Status: approved 2 km² downtown pilot. Not a city-wide change claim.

## AOI and data

- Bounds: `E492000–E494000, N5456000–N5457000`, 2 km².
- 2018 City LiDAR tiles: `4920E_54560N.zip`, `4930E_54560N.zip`.
- 2018 acquisition: 2018-08-27/28, about 30 points/m².
- 2022 later surface: P30 City of Vancouver 2022 1 m CHM.
- Grid: 1 m EPSG:3157, 2,000 × 1,000 cells.
- Canopy threshold: 2 m.

The 2018 LAS tiles were downloaded through a headed Chromium session under Xvfb;
plain HTTP clients receive HTTP 403. Raw data stays under `/srv/shared-data`.

Tile checksums:

| Tile | SHA-256 |
| --- | --- |
| `4920E_54560N.zip` | `33e85edd9c0906cfae16db2fc71cfa14b0beae406ac2610c511c086d73f98ed9` |
| `4930E_54560N.zip` | `e73507b2efbd28fdf79f0912cbf86d21eef4a6079df821c50746da3441cedc5f` |

## Method

- 2018 ground surface: minimum z of class-2 points per 1 m cell, nearest-filled.
- 2018 canopy surface: maximum z of class-3 and class-5 vegetation points.
- 2018 CHM: canopy minus ground, clipped at zero.
- 2022 CHM: P30 1 m CHM.
- Valid overlap: both dates finite.
- Classes: stable, gain, loss, no canopy.
- 400 m cells are aligned to the global P38 grid; partial edge cells are reported.

The 2018 class-1 unclassified points were not used as canopy. This is conservative
and may undercount canopy relative to the 2022 all-canopy CHM.

## Result

- Earlier canopy: **440,509 m²**
- Later canopy: **498,871 m²**
- Gain: **68,844 m²**
- Loss: **10,482 m²**
- Stable: **430,027 m²**
- Net: **+58,362 m²**
- Gain: **+15.63%** of earlier canopy
- Loss: **−2.38%** of earlier canopy
- Mean height change on stable canopy: **+0.604 m**
- 400 m cells: **18** (partial global grid at the AOI edge)
- Change class: all 18 cells are net gain under the 5% threshold

The 18 cells join the P38 shade/equity, P39 gap/opportunity, and P40 LST/heat-equity
cells. Those joins are descriptive overlays, not causal evidence.

## Products

Under `data/processed/change_vancouver_2018_2022_downtown/`:

- `change.json`, `change.png`, `change_grid.npz` — 1 m change product
- `canopy_change.json`, `canopy_change.geojson`, `canopy_change.png` — 400 m product
- `canopy_change_meta.json` — methods and caveats

API: `/api/canopy-change` and `/api/canopy-change.geojson`. Map: **canopy change**
toggle and sidebar summary.

## Limits

- **Not tree survival or growth.** A thresholded LiDAR difference is not a survival,
  planting, removal, or species record.
- **Acquisition and datum differences.** 2018 and 2022 differ in point density,
  classification, date, and vertical handling.
- **Conservative 2018 canopy.** Class-1 unclassified points are excluded.
- **Small-AOI pilot.** The two-tile downtown AOI is not a city-wide change claim.
- **No causal attribution.** No ownership, policy, or planting-program claim.

## Browser smoke

The map loaded the 18-cell product, the **canopy change** toggle worked, the sidebar
showed +6 ha net, 7 ha gain, 1 ha loss, and 43 ha stable canopy, with no console or
page errors.
