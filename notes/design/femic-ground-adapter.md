# Optional FEMIC ground-adapter design

Status: design note, 2026-11-04. P15.2. Accepted by P15.3; not implemented.

## Purpose

Define an optional, versioned boundary between the MIT-licensed ground-classification lane
in `fresh-urban-forest-lab` and FEMIC's LidarBC product world. The adapter produces a
**sidecar ground bundle** for one ALS tile. It does not change FEMIC's default products,
does not import FEMIC, and does not become a core dependency.

This is a design for a prototype adapter. It is not a production integration.

## Boundary

```text
LidarBC LAZ/COPC tile
        |
        v
fresh-urban-forest-lab ground lane
  SOR -> PTD -> low-point flag
        |
        v
sidecar bundle:
  ground.laz
  manifest.json
  qa.json
        |
        v
optional FEMIC reader / future product lane
```

FEMIC owns its default product path. The adapter owns only the sidecar bundle. A FEMIC
consumer may read the bundle later, but the bundle is valid on its own.

## Input contract

Required:

- `laz_path`: one local LAZ or COPC file;
- `out_dir`: explicit output directory;
- `crs`: EPSG code or WKT, recorded even when the LAZ header has one;
- `vertical_datum`: explicit label, recorded even when the header has one.

Parameters, with defaults:

- `sor_k = 10`
- `sor_multiplier = 2.0`
- `cell_size_m = 1.0`
- `max_angle_deg = 15.0`
- `max_distance_m = 0.5`
- `max_iterations = 8`
- `low_point_cut_m = 0.15`
- `sor_enabled = true`

The adapter records the parameter hash. It does not silently infer a missing CRS or vertical
datum; a missing value is a warning and an explicit `null` in the manifest.

## Output bundle

```text
<out_dir>/
  ground.laz
  manifest.json
  qa.json
```

`ground.laz` is a copy of the input with extra dimensions:

| Dimension | Type | Meaning |
| --- | --- | --- |
| `is_ground` | uint8 | 1 = predicted ground, 0 = not ground |
| `hag` | float32 | height above the predicted ground surface, metres |
| `is_low` | uint8 | 1 = below the low-point cut |
| `ref_class` | uint8 | original LAS classification, copied for traceability |

The LAZ copy keeps the original CRS and vertical datum fields. It does not change the
geometry.

`manifest.json` schema: `femic.ground-bundle.v1`.

```json
{
  "schema_version": "femic.ground-bundle.v1",
  "created_utc": "2026-11-04T00:00:00Z",
  "source": {
    "path": "tile.laz",
    "sha256": "<input hash>",
    "crs": "EPSG:2955",
    "vertical_datum": "CGVD2013",
    "point_count": 113775
  },
  "output": {
    "path": "ground.laz",
    "sha256": "<output hash>",
    "point_count": 113775
  },
  "parameters": {
    "sor_enabled": true,
    "sor_k": 10,
    "sor_multiplier": 2.0,
    "cell_size_m": 1.0,
    "max_angle_deg": 15.0,
    "max_distance_m": 0.5,
    "max_iterations": 8,
    "low_point_cut_m": 0.15
  },
  "parameter_sha256": "<canonical parameter hash>",
  "method": {
    "name": "ptd-inspired-ground",
    "version": "fresh-urban-forest-lab ground lane",
    "reference": "Axelsson 2000; Arbor book chapter 4",
    "clean_room": "independent Python implementation; no Arbor or lidR code copied"
  },
  "qa": {
    "path": "qa.json",
    "sha256": "<qa hash>"
  },
  "warnings": []
}
```

`qa.json` schema: `femic.ground-qa.v1`.

Required fields:

- point count, ground count, low-point count;
- SOR removed count and fraction;
- seed count, iteration count, TIN warning;
- HAG percentiles (p0, p1, p5, p25, p50, p75, p95, p99, max);
- class counts for the original classification;
- predicted-ground fraction by original class;
- runtime seconds;
- parameter hash;
- explicit `ground_truth_used: false` and a note that no accuracy claim is attached.

## CLI shape

```bash
fresh-urban-forest ground-adapter \
  --laz tile.laz \
  --out build/ground/tile \
  --crs EPSG:2955 \
  --vertical-datum CGVD2013 \
  --sor \
  --low-point-cut 0.15
```

The command is opt-in. It is not part of `build`, `serve`, or the default dataset pipeline.

## Dependency boundary

- No hard FEMIC dependency.
- No FEMIC import in the core package.
- No new runtime dependency is required: `laspy`, `numpy`, and `scipy` are already used.
- A future FEMIC reader is a separate optional integration and needs its own design review.
- The adapter is not an entry point in FEMIC's provider registry in this phase.

## Failure modes and warnings

| Condition | Behaviour |
| --- | --- |
| Missing CRS | Record `null`, add warning, continue |
| Missing vertical datum | Record `null`, add warning, continue |
| Fewer than 3 ground seeds | Seed-only result, warning in QA |
| Degenerate TIN | Seed-only result, warning in QA |
| Fewer than 100 class-2 points | Continue, warning that class-2 QA is weak |
| SOR removes more than 10% of points | Continue, warning |
| Output exists | Refuse unless `--overwrite` |
| Input hash mismatch | Refuse to reuse an existing manifest |
| Empty cloud | Refuse, non-zero exit |

No warning is silently dropped. The manifest and QA file carry the same warning list.

## Versioning

- Bundle schema: `femic.ground-bundle.v1`.
- QA schema: `femic.ground-qa.v1`.
- Parameter hash: canonical JSON of the parameter block.
- Code version: package version plus git commit in the manifest.
- A schema change is a new version, not an in-place edit.

## Test strategy

1. **Unit:** synthetic point cloud with known ground/vegetation; SOR, PTD, low-point flag.
2. **Contract:** tiny synthetic LAZ in a fixture; write bundle; validate manifest and QA
   schemas; assert hashes and dimensions.
3. **Failure:** missing CRS, degenerate TIN, output collision, empty cloud, SOR warning.
4. **Golden-tile smoke:** one real LidarBC tile in `runtime/`, not committed; assert bundle
   exists and QA fields are populated.
5. **No network in CI.** The real-tile smoke test is manual or an optional local job.

## Non-goals

- No default FEMIC product change.
- No automatic classification of every LidarBC tile.
- No claim that the ground labels are noise-free.
- No replacement for a manually labelled reference patch or a full terrain suite.
- No hard dependency on FEMIC or Arbor.

## Open questions

1. Should the bundle use a copied LAZ with extra dimensions or a sidecar Parquet table? The
   LAZ copy is simpler for LAS-native consumers; Parquet is easier for tabular joins.
2. Should the reference class-2 QA be optional in production? The adapter should not
   require class 2, but it should record when class 2 is absent.
3. Does FEMIC want a reader in its core, an optional plugin, or an external ingestion step?
   That is a FEMIC-side decision, not this adapter's.
