# P43 citywide observed canopy change 2018–2022

Status: citywide product built; API/map and browser smoke verified.

This is a repeat-measures LiDAR comparison, not tree survival, growth, species change,
ownership, or causal attribution.

## 2018 tile audit

- 181 ZIP tiles present.
- Total compressed volume: **78,035,756,093 bytes (72.68 GiB)**.
- SHA-256, size, and ZIP integrity records:
  `data/raw/tiles/vancouver_2018_city_checksums.csv` (ignored raw data).
- Corrupt archives: **0**.
- Coverage inside the P30 boundary: **118.717 / 118.763 km² (99.96%)**.
- Source: City of Vancouver LiDAR 2018, acquired 2018-08-27/28, nominal 30 points/m².

## Citywide build

- 5 m EPSG:3157 citywide grid.
- One ZIP extracted at a time; temporary LAS removed.
- Point stride **32** applied consistently for tractability.
- Ground: class-2 minimum z; canopy: class-3/5 maximum z.
- 2018 CHM = canopy − filled ground, clipped at zero.
- 2022 CHM: P30 1 m CHM resampled to the same 5 m grid.
- Canopy threshold: **2 m**.
- Process metadata: `change_process.json` records 181 tiles, 6,443,969,191 points read,
  and 201,374,126 sampled points.

## Outputs

Directory: `data/processed/change_vancouver_2018_2022_citywide/`

- `change.json` — summary, metrics, bounds, and valid overlap.
- `change.png` — change class overlay.
- `change_grid.npz` — 5 m earlier/later/change/valid grids.
- `earlier_chm_2018.tif`, `later_chm_2022.tif`, `valid_overlap.tif`.
- `change_process.json` — sampling and point counters.
- `canopy_change.json`, `canopy_change.geojson`, `canopy_change.png` — 797 400 m cells
  joined to P38 shade/equity, P39 gaps, P40 heat equity, and P42 action fields.

## Citywide change metrics

- earlier canopy: **32,912,355.6 m²**
- later canopy: **30,748,704.8 m²**
- gain: **889,357.6 m²**
- loss: **3,053,008.4 m²**
- stable canopy: **29,859,347.2 m²**
- net: **−2,163,650.9 m²**
- gain as share of earlier canopy: **2.70%**
- loss as share of earlier canopy: **9.28%**
- mean height change on stable canopy: **−1.51 m**
- valid overlap: **35,697,214.2 m²**

The negative height change is not interpreted as tree health or growth. The 2018 and 2022
surfaces differ in acquisition season, classification, density, vertical datum, and
co-registration. The thresholded surface change is a screening signal.

## Limits

- Sampling stride 32 reduces point density; this is a screening surface, not a full
  point-cloud reprocessing.
- 2018 class-1 unclassified points are excluded from canopy.
- Citywide valid overlap is about 35.7 km², not the nominal 118.8 km² city area.
- No tree survival, species, ownership, causal, or field-validation claim.
