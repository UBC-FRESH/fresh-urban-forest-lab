# P38 shade and social-equity screening

Status: active. This is a public-data screening product, not a CanopyFit
replication, a planting permit, or a private-tree census.

## What was reproduced

The published CanopyFit workflow (Nixon et al., 2026,
`doi:10.1016/j.ufug.2026.129668`) uses a digital surface model, solar radiation, a
400 m grid, a tree-equity index, and median splits into eight priority classes. Its
code, 50 cm land-cover product, municipal utility constraints, and consulting equity
data are not public. This phase reimplements only the transferable method:

- raster shade from public LiDAR canopy and building surfaces;
- a 400 m grid with shade deficit, canopy cover, and shade efficiency;
- a population-weighted Census equity screen; and
- median splits into `1A` to `4B`, with `A` meaning high shade efficiency.

It does not reproduce the proprietary inputs or the exact CanopyFit outputs.

## Inputs

| Input | Source | Role |
| --- | --- | --- |
| 2022 DEM, CHM, DSM, building height, masks | City of Vancouver LiDAR / P30 processed dataset | Ground, canopy, buildings, water |
| 2021 Census Profile, dissemination areas | Statistics Canada SDMX Census Profile API | Income, age dependency, visible-minority share, unemployment |
| 2021 dissemination-area boundaries | Statistics Canada 2021 DA feature service | Population-weighted areal interpolation |

The raw Census files and the generated product stay under `/srv/shared-data` and
are not committed. The code and method note are in git.

## Method

1. Resample the public LiDAR surfaces to a 5 m grid over the Vancouver bounds.
2. At eight local summer samples (15 July and 15 August, 10:00, 12:00, 14:00, 16:00),
   ray-march 200 m toward the sun at 5 m spacing.
3. Mark a target cell as tree-shaded when a sampled canopy top rises above the
   pedestrian target plus the solar elevation over that distance; repeat for
   buildings. The two masks are kept separate and combined by union.
4. Accumulate shade fractions and aggregate to 400 m cells.
5. Compute canopy cover from the CHM at 2 m or taller, excluding building and water
   masks; compute canopy volume from the CHM; compute shade efficiency as
   tree-shade area-hours per cubic metre of canopy.
6. Build the equity score from four 2021 Census indicators at dissemination-area
   level:
   - median household income (higher income = lower need);
   - age dependency, `(0–14 + 65+) / 15–64`;
   - visible-minority share; and
   - unemployment rate.
7. Rank each indicator across Vancouver dissemination areas, average the four need
   percentiles, and interpolate to 400 m cells using population weights.
8. Split shade deficit, equity, and shade efficiency at their city medians into
   eight classes. `1A` is high deficit, high equity need, high efficiency; `4B` is
   low deficit, low equity need, low efficiency.

The solar model is opaque geometry: no leaf transmissivity, penumbra, facade
reflections, or observed weather. The shade number is a relative screening surface,
not a temperature or irradiance measurement.

## Vancouver result

Run on the P30 Vancouver 2022 dataset with the public Census inputs:

- 797 populated 400 m cells inside scored dissemination areas.
- Mean combined shade: 24.9%.
- Mean tree shade: 16.8%.
- Mean building shade: 9.4%.
- Mean sunlit fraction: 75.1%.
- 1,018 dissemination areas loaded; 1,017 received an equity score.
- Census population represented: 662,731.
- Class counts: `1A` 48, `1B` 207, `2A` 55, `2B` 89, `3A` 89, `3B` 55,
  `4A` 207, `4B` 47.
- Win-win cells (`1A` + `1B`): 255.

The 2022 City of Vancouver published canopy-cover estimate is about 25%; the P30
CHM estimate is 26.85%. The shade estimate is not calibrated to that cover number.

## Products

Generated under `data/processed/vancouver_2022/`:

- `heat_priority.json` — full cell records and metadata;
- `heat_priority.geojson` — 400 m cells in WGS84;
- `heat_priority.png` — class-coloured transparent grid;
- `heat_priority_meta.json` — methods, samples, equity summary, and caveats.

The API exposes `/api/heat-priority` and `/api/heat-priority.geojson` only when the
dataset contains the product. The map has a **shade equity** toggle and a sidebar
summary.

## Reproduce the Census inputs

The exact public endpoints used were:

```text
# 2021 Census Profile, dissemination areas
https://api.statcan.gc.ca/census-recensement/profile/sdmx/rest/data/STC_CP,DF_DA,1.3/A5..1.<characteristic>.<statistic>?startPeriod=2021&endPeriod=2021&format=csv

# Characteristic / statistic pairs
population 1/1
age 0-14 9/1
age 15-64 13/1
age 65+ 24/1
median household income 113/1
visible-minority total 1669/1
visible minority 1670/1
unemployment rate 2230/4
```

The DA geometry came from the public `DisseminationAreas` feature service
(`services.arcgis.com/wjcPoefzjpzCgffS`) over a Vancouver bounding box, then filtered
to the City boundary. The prepared files are named `cp_<characteristic>.<statistic>.csv`
and `da_geometry_vancouver.geojson` under `data/raw/census_2021/`.

Build the product:

```bash
python scripts/build_vancouver_heat_priority.py \
  --root data/processed/vancouver_2022 \
  --census-dir data/raw/census_2021 \
  --out data/processed/vancouver_2022 \
  --resolution 5 \
  --cell-size 400
```

## Limits

- **No land-surface temperature.** The equity score is social, not a heat-vulnerability
  index. A later phase can add open Landsat/Sentinel LST and a separate heat-exposure
  layer.
- **No planting feasibility.** Utilities, ownership, setbacks, soil volume, access,
  sports fields, wildfire buffers, and sensitive ecosystems are not available as
  public city-wide layers. Shade deficit is not plantable area.
- **No private-tree census or ownership claim.** Canopy comes from LiDAR, not from
  parcel records.
- **No field validation.** The shade model has not been checked against measured
  irradiance or pedestrian thermal comfort.
- **No exact CanopyFit reproduction.** The code, land-cover product, and consulting
  equity inputs are missing; this is an independent method implementation.

## Next

- Add open Landsat/Sentinel land-surface temperature and compare it with the shade
  deficit.
- Add a canopy-gap/planting-opportunity layer only with an explicit above-ground
  constraint model.
- Validate the shade surface against a small field or pyranometer sample if one
  becomes available.
