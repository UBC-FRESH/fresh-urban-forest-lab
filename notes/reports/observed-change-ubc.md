# Observed canopy change: UBC 2015/2016 to 2021

Status: first two products, 2026-11-03.

## Products

### UBC LiDAR 2015 ↔ UBC LiDAR 2021

- Source: four UBC 2015 LAZ tiles (`UBC_481_5456`, `UBC_481_5457`, `UBC_482_5456`,
  `UBC_482_5457`), EPSG:26910, transformed to the 2021 EPSG:3157 DEM grid.
- Earlier canopy: 2.36M m²
- Later canopy: 2.47M m²
- Gain: +320,535 m²
- Loss: −209,369 m²
- Stable: 2.15M m²
- Net: **+111,166 m²**
- Mean height change on stable canopy: **+0.235 m**
- Valid overlap: 4.00M m²

### LidarBC 2016 ↔ UBC LiDAR 2021

- Source: four LidarBC 2016 tiles covering the campus core, EPSG:3157.
- Earlier canopy: 4.57M m²
- Later canopy: 4.76M m²
- Gain: +384,143 m²
- Loss: −199,042 m²
- Stable: 4.38M m²
- Net: **+185,101 m²**
- Mean height change on stable canopy: **+0.949 m**
- Valid overlap: 7.51M m²

## What this means

Both comparisons show a net canopy gain, but the magnitudes differ. The products cover
different areas and use different source acquisitions, vertical datums, and seasons. They
are **not** two independent estimates of the same quantity and should not be averaged.

The 2015 product is a useful second screening surface, but a direct 2015↔2016 comparison
on the same mask is needed to separate real one-year change from acquisition and datum
differences.

## Caveats

- The 2015 tiles are EPSG:26910; the 2021 DEM is EPSG:3157. Point coordinates were
  transformed before binning.
- Vertical datums and acquisition seasons differ.
- The change threshold is 2 m.
- A canopy gain does not prove new planting; it can reflect growth, crown expansion,
  better returns, or a method difference.
- Loss can reflect removal, dieback, pruning, shadow, or a lower-quality return.

## Next

1. Build 2015 and 2016 on the same mask and grid, then compare 2015↔2016.
2. Add the 2015 product to the Change tab selector (done).
3. Keep the field packet as the route to a complete-reference patch.
