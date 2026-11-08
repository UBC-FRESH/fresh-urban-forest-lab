# P43 2018 LiDAR checksum and audit

Date: 2026-11-08

Status: complete.

## Result

- 181 / 181 ZIP tiles present.
- Total compressed size: **78,035,756,093 bytes (72.68 GiB)**.
- 181 / 181 ZIPs passed `zipfile.testzip()`.
- Every tile has size and SHA-256 in
  `data/raw/tiles/vancouver_2018_city_checksums.csv`.
- Missing or corrupt archives: **none**.

The downloaded tiles have 99.96% union coverage of the P30 city boundary
(118.717 / 118.763 km²). Index coverage is not the same as validated LAS point
coverage; P43.2 still has to verify extracted LAS content and build the citywide CHM.

## Raw data

- Tiles: `data/raw/city_lidar/2018/vancouver-lidar-2018/`
- Index: `data/raw/tiles/vancouver_2018_city.json`
- Checksums: `data/raw/tiles/vancouver_2018_city_checksums.csv`

Raw data is ignored. The shared tile tree is used by P41 and P43.
