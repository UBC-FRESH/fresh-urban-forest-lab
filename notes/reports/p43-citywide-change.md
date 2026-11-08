# P43 citywide observed canopy change 2018–2022

Status: citywide 2 m screening product built; close-out pending.

## 2018 tile audit

- 181 ZIP tiles present.
- Total ZIP volume: **78.0 GB**.
- SHA-256 and ZIP-member audit: `data/raw/tiles/vancouver_2018_checksums.json` (ignored).
- Corrupt archives: **0**.
- Source: City of Vancouver LiDAR 2018, acquired 2018-08-27/28, nominal 30 points/m².

## Method

- 2 m EPSG:3157 citywide grid.
- One ZIP extracted at a time; temporary LAS removed.
- Point stride 16, applied consistently.
- 2018 canopy: maximum class-3/5 elevation; class-1 unclassified points excluded.
- 2018 ground: P30 2022 DEM plus a **+1.0 m** vertical offset estimated from the
  downtown 2018 ground/2022 DEM difference.
- 2022 later surface: P30 1 m CHM, NaN treated as zero inside the AOI, excluding
  buildings and water.
- Threshold: 2 m.
- Change: stable, gain, loss, no canopy; aggregated to the global P38 400 m cells.

### Why 2 m, not 5 m

A 5 m maximum aggregation inflated the 2018 canopy edge area because a single 1 m
canopy point filled a 5 m cell while the 2022 CHM was sampled nearest. The 5 m run
produced a 28.8% apparent loss and was rejected as scale-biased. The 2 m run is still a
screen, but its 2018 canopy cover (24.97%) is consistent with the 2022 P30 cover
(26.85%) and the City's published ~25% check.

## Result

- Earlier canopy: **29,652,451 m²** (2,965.25 ha)
- Later canopy: **31,886,460 m²** (3,188.65 ha)
- Gain: **5,241,589 m²** (524.16 ha)
- Loss: **3,007,581 m²** (300.76 ha)
- Stable: **26,644,870 m²** (2,664.49 ha)
- Net: **+2,234,009 m²** (**+223.40 ha**)
- Gain: **17.68%** of earlier canopy
- Loss: **10.14%** of earlier canopy
- Mean height change on stable canopy: **+1.475 m**
- 797 global 400 m cells; all join P38–P42 fields.

The product is a repeat-measures LiDAR comparison. It is not tree survival, growth,
species change, ownership, or causal attribution.

## Products

Under `data/processed/vancouver_2022/`:

- `canopy_change.json`
- `canopy_change.geojson`
- `canopy_change.png`
- `canopy_change_meta.json`

Source change grid: `data/processed/change_vancouver_2018_2022_citywide_2m/`.

API: `/api/canopy-change` and `/api/canopy-change.geojson`. Map: **canopy change**
toggle and sidebar summary.

## Limits

- **2 m max-vs-nearest comparison.** 2018 uses maximum canopy elevation; 2022 uses the
  P30 CHM. Scale and edge effects remain.
- **Vertical offset.** The +1.0 m DEM offset is estimated, not surveyed per tile.
- **Sampling.** Stride 16 reduces point density.
- **Class-1 exclusion.** 2018 unclassified points are excluded; earlier canopy may be
  conservative.
- **No tree survival, species, ownership, causal, or field-validation claim.**

## Post-hoc sensitivity (P45)

P45 shows the citywide net sign is not stable across a ±1.0 m offset range:
from about −99 ha to +488 ha. Do not claim a net gain or loss from this screen
without external vertical control. See `notes/reports/p45-change-sensitivity.md`.
