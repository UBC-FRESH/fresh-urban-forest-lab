# Observed canopy change: City of Vancouver 2018 ↔ 2022

Status: first City repeat-measures product, 2026-11-03.

## Getting the tiles past Cloudflare

`webtransfer.vancouver.ca` returns a Cloudflare 403 to `curl`, `httpx`, and headless
Chromium from the server. A **headed** Chromium launched under Xvfb passed the challenge
and downloaded the ZIPs normally.

Operator command:

```bash
xvfb-run -a python scripts/browser_download_tiles.py \
  --manifest data/raw/tiles/vancouver_2022_ubc.json \
  --dest data/raw/city_lidar/2022
```

Tiles downloaded for the UBC core:

| Year | Tiles | ZIP size |
| --- | --- | ---: |
| 2018 | `4810E_54560N.zip`, `4820E_54560N.zip` | 547 MB, 565 MB |
| 2022 | `481000_5456000.zip`, `482000_5456000.zip` | 1.02 GB, 0.98 GB |

The script does not bypass authentication. It uses a normal browser session; the access
policy and the Cloudflare challenge remain the publisher's.

## Product

- Bounds: `E481000–E483000, N5456000–N5457000`, 1 m grid.
- 2018 LAS: EPSG:3157, classes 1/2/3/5/6/7/9.
- 2022 LAS: EPSG:26910, transformed to EPSG:3157 before binning.
- Ground, buildings, water, and noise excluded from the canopy surface.
- Threshold: 2 m.

| Metric | Value |
| --- | ---: |
| Earlier canopy (2018) | 728,756 m² |
| Later canopy (2022) | 864,335 m² |
| Gain | +212,734 m² |
| Loss | −77,155 m² |
| Stable | 651,601 m² |
| Net | **+135,579 m²** |
| Mean height change on stable canopy | **+0.575 m** |
| Valid overlap | 2.00M m² |

## Interpretation

- The City product shows a net gain of about 13.6 ha over four years in the two core
  tiles.
- The gain is larger in percentage terms than the UBC 2015→2021 product (29% of earlier
  canopy vs 4.7–9.9% in the UBC products). The City product covers a different, more
  developed area and uses a different acquisition/classification chain; do not read the
  percentages as directly comparable.
- Both 2018 and 2022 are late-summer acquisitions, which reduces the leaf-on/leaf-off
  confound relative to a winter-to-summer comparison.
- The vertical datum is CGVD28GVRD for the City products; the UBC 2021 product uses a
  different vertical reference. The comparison is a screening surface, not a calibrated
  growth rate.

## Status in the app

The product is available in the Change tab selector as
`City of Vancouver LiDAR 2018 → City of Vancouver LiDAR 2022`.
