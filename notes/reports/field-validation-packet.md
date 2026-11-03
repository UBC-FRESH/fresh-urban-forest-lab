# Field validation packet: Main Mall patch

Status: packet generated, field work not yet done.

## Patch

- Bbox: `-123.255,49.258,-123.245,49.265`
- Inventory trees in packet: 200
- Detected crowns in patch: 3,966
- One-to-one matches at 5 m: 1,268

## Command

```bash
fresh-urban-forest field-packet \
  --dataset data/processed/ubc_lidar_2021 \
  --chm data/raw/ubc/lidar_2021/CHM_1m.tif \
  --bbox -123.255,49.258,-123.245,49.265 \
  --min-height 3 \
  --window 6 \
  --max-trees 200 \
  --out-dir data/processed/field_packet_mainmall
```

## Files

- `field_trees.geojson`: inventory trees.
- `detected_crowns.geojson`: detected crowns.
- `field_checks.csv`: one row per inventory tree, with measured flags, detected match,
  blank field measurement columns, and `field_verified` / `field_notes`.
- `detected_checks.csv`: one row per detected crown, with blank `field_status` and
  `field_notes`. Use `real`, `merged`, or `false_positive`.
- `README.md`: field protocol.

After the field crew completes the CSVs:

```bash
fresh-urban-forest analyze-field-packet   --packet data/processed/field_packet_mainmall   --out-dir data/processed/field_packet_mainmall/analysis
```

The analysis reports precision, precision including merged crowns, recall, missing and new
trees, and height/crown bias. It only uses field-verified rows.

## Why this matters

The whole-inventory precision number (0.217–0.239) is not a true error rate because the
inventory is incomplete. This packet is the start of a **complete-reference patch** where
every live tree and every detected crown is verified by a person. The completed CSV will
support:

- detection precision and recall against a complete patch;
- height and crown-width bias;
- inventory omission and commission;
- the share of the canopy estimate that depends on imputed attributes.

## Caveat

The packet has not been field-verified. It is a protocol and a candidate patch, not a
validated reference.
