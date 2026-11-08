# P41 2018 LiDAR index and coverage audit

Status: acquisition audit complete; full 2018 download not started.

## Source

City of Vancouver Open Data, **LiDAR 2018**:

- 181 tile polygons / ZIP links
- acquired 2018-08-27 and 2018-08-28
- nominal density 30 points/m²
- vertical accuracy 0.18 m at 95% confidence
- horizontal accuracy 0.36 m at 95% confidence
- LAS coordinate system: UTM Zone 10, NAD83 (CSRS) 4.0.0.BC.1.GVRD,
  vertical datum CGVD28GVRD
- ZIP sizes range from 7 KB to 950 MB
- portal: https://opendata.vancouver.ca/explore/dataset/lidar-2018/

## Audit result

Generated with:

```bash
python scripts/audit_vancouver_2018_lidar.py \
  --out data/raw/tiles/vancouver_2018_city.json \
  --boundary data/processed/vancouver_2022/boundary.geojson \
  --existing data/raw/city_lidar/2018
```

Result:

- full index: **181 tiles**
- city boundary area: **118.763 km²**
- tile-union coverage inside the boundary: **118.717 km²**
- coverage fraction: **99.96%**
- downloaded: **2 tiles**
- downloaded coverage inside the city boundary: **0.0 km²**
- missing: **179 tiles**

The two present tiles are the UBC-subset tiles from the earlier pilot. They do not
cover the City of Vancouver boundary used by P30.

## Blocker

`webtransfer.vancouver.ca` returns HTTP 403 to plain `curl`/`httpx` clients. The
existing operator path is:

```bash
xvfb-run -a python scripts/browser_download_tiles.py \
  --manifest data/raw/tiles/vancouver_2018_city.json \
  --dest data/raw/city_lidar/2018
```

The full collection is expected to be tens of gigabytes and 181 browser downloads.
That is an explicit operator/time/storage decision, not something to start silently.

## Next

1. Approve the full 2018 download or select a smaller AOI.
2. Download and checksum the chosen tiles.
3. Record actual tile sizes, checksums, and successful coverage.
4. Only then start P41.2 aligned CHMs.

## Limits

- Index coverage is not the same as downloaded data coverage.
- The two existing tiles do not support a city-scale change claim.
- No 2018→2022 change has been computed in this task.
