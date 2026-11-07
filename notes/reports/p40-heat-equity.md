# P40 open land-surface temperature and heat equity

Status: active. This is a Landsat surface-temperature screening layer, not air
temperature, pedestrian thermal comfort, a health outcome model, or a planting plan.

## What it does

The product uses public Landsat 8/9 Collection 2 Level-2 surface temperature
(`ST_B10`) and `QA_PIXEL` from the Microsoft Planetary Computer. It:

- reprojects scenes to the P38 Vancouver grid at 30 m;
- applies the Collection 2 scale/offset (`0.00341802`, `149.0 K`) and converts to °C;
- masks fill, dilated cloud, cirrus, cloud, cloud shadow, snow, water, building
  rooftops, and implausible values;
- takes a pixel-wise median across five summer scenes;
- aggregates mean and 90th-percentile LST to the P38 400 m cells; and
- combines LST with the P38 four-indicator social score as a five-part,
  equal-weight index.

The index is deliberately not called a validated TESPI: the four social indicators
enter through the P38 mean, and LST is the fifth equal-weight component. It is a
relative screen.

## Scenes

| Scene | Date | Cloud cover | Valid pixels |
| --- | --- | --- | ---: |
| `LC08_L2SP_048026_20220624_02_T1` | 2022-06-24 | 0.49% | 114,586 |
| `LC09_L2SP_047026_20220711_02_T1` | 2022-07-11 | 1.49% | 115,385 |
| `LC08_L2SP_048026_20220726_02_T1` | 2022-07-26 | 0.22% | 114,280 |
| `LC09_L2SP_047026_20220727_02_T1` | 2022-07-27 | 2.05% | 115,145 |
| `LC08_L2SP_048025_20220811_02_T1` | 2022-08-11 | 20.05% | 51,968 |

The August scene is partly cloud-affected over Vancouver; the median composite
retains the clearer July observations where available.

## Vancouver result

- 797 400 m cells.
- Mean LST: **37.67 °C**.
- Median LST: **38.51 °C**.
- Range of cell means: **23.32–45.12 °C**.
- Mean cell p90: **39.65 °C**; maximum p90 **48.44 °C**.
- Heat-equity tiers: **high 305**, **medium 289**, **low 203**.
- Hottest cell: `r23c20`, 45.12 °C, but P38 class `3A` (low shade-equity need).
- Highest heat-equity index: `r19c31`, 43.5 °C, P38 class `1B`, social score 0.87.

This divergence is the point: the hottest surface is not automatically the highest
equity priority, and the highest equity priority is not automatically the hottest
surface.

## Products

Generated under `data/processed/vancouver_2022/`:

- `heat_equity.json` — 400 m cells and metadata;
- `heat_equity.geojson` — WGS84 cells;
- `heat_equity.png` — transparent tier grid;
- `heat_equity_meta.json` — scenes, scale/offset, methods, and caveats.

The API exposes `/api/heat-equity` and `/api/heat-equity.geojson` only when the
product exists. The map has a **heat equity** toggle and a sidebar summary.

## Reproduce the Landsat inputs

The public Planetary Computer STAC endpoint was queried for
`landsat-c2-l2` over the Vancouver bbox, June–September 2022. Asset URLs were
signed with the public container token:

```text
GET https://planetarycomputer.microsoft.com/api/sas/v1/token/landsateuwest/landsat-c2
```

The `token` field was appended to each `lwir11` and `qa_pixel` asset URL. Five
scenes with low cloud cover were downloaded. Raw scenes (~400 MB) stay under
`/srv/shared-data` and are not committed.

Build:

```bash
python scripts/build_vancouver_heat_equity.py \
  --root data/processed/vancouver_2022 \
  --landsat-dir data/raw/landsat_2022 \
  --heat-priority data/processed/vancouver_2022/heat_priority.json \
  --out data/processed/vancouver_2022 \
  --resolution 30 \
  --cell-size 400
```

## Limits

- **LST is not air temperature or thermal comfort.** It is a satellite surface
  retrieval at the overpass time.
- **Cloud and mixed pixels remain.** The August scene is partly cloud-affected.
- **Rooftops and water are excluded**, but other hot surfaces remain.
- **The social index is relative.** It is not a validated vulnerability or health
  model.
- **No utilities, ownership, access, soil, irrigation, cost, or field validation.**
- **Not a CanopyFit replication.** No proprietary code or tree-equity data are used.
