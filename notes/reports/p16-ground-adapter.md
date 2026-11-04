# P16 ground-adapter implementation

Date: 2026-11-04
Phase: P16
Parent issue: #103
Task: #104
Status: implemented; opt-in; no default FEMIC product change

## Implemented

`src/fresh_urban_forest/ground_adapter.py`:

- `GroundAdapterParameters` with a canonical `sha256()`;
- `GroundBundleResult`;
- `write_ground_bundle`;
- versioned `femic.ground-bundle.v1` and `femic.ground-qa.v1` schemas.

The writer copies the input LAZ and adds:

| Dimension | Type | Meaning |
| --- | --- | --- |
| `is_ground` | uint8 | predicted ground |
| `hag` | float32 | height above the predicted surface; NaN for SOR-removed points |
| `is_low` | uint8 | below the low-point cut |
| `ref_class` | uint8 | original LAS classification |

CLI: `fresh-urban-forest ground-adapter --laz ... --out ...`.

The adapter is not part of `build`, `serve`, or the default dataset path. It does not import
FEMIC.

## Contract tests

`tests/test_ground_adapter.py` covers:

- nominal bundle creation;
- manifest and QA schemas;
- input/output hashes;
- extra-dimension alignment;
- missing CRS and vertical-datum warnings;
- overwrite refusal and explicit overwrite;
- empty input;
- CLI invocation.

## Real-tile smoke test

Golden-area tile `bc_082n025_4_2_1_xyes_8_utm11_2021.laz`:

- points: 113,775;
- predicted ground: 82,530;
- low-point flag: 78,965;
- SOR removed: 5,355;
- seed points: 3,693;
- iterations: 8;
- HAG p50: 0.0176 m;
- HAG p90: 2.078 m;
- HAG p99: 5.6293 m;
- warnings: none;
- runtime: 5.8 s.

The low-point count is high because the tile has many near-ground points. It is a downstream
flag, not a claim that 69% of the tile is invalid.

## Limits

- The smoke test is local; it is not a CI network job.
- The classifier remains a simplified PTD-inspired implementation.
- The bundle is a sidecar, not a FEMIC product.
- The low-point flag is not a ground label.
- No tag or release is included.
