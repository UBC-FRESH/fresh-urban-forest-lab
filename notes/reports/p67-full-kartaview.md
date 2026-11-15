# P67 full live-host KartaView pass

Status: data published; code and documentation PR pending merge.

## Coverage

- Same 118-cell, 1 km boundary grid with a 500 m query radius.
- Metadata audit: 10,204 unique KartaView records.
- 3,772 records point at `storage1.openstreetcam.org`; sampled blobs return
  `BlobNotFound`, so those records were excluded.
- 6,425 live-host records were selected, spanning all 117 populated cells.
- 6,425 images decoded; no download failures in the final pass.

Storage-host selection:

| Host | Selected images |
| --- | ---: |
| storage3 | 2,724 |
| storage4 | 1,357 |
| storage5 | 813 |
| storage6 | 465 |
| storage7 | 322 |
| storage11 | 330 |
| storage8 | 237 |
| storage9 | 99 |
| storage12 | 55 |
| storage13 | 23 |

Coverage details: `notes/reports/p67-coverage-summary.json`.

## Run

- Full live-host set processed with OneFormer ADE20K and ZoeDepth NYU-KITTI.
- Images were decoded and inferred in batches of eight.
- Detections were persisted incrementally before fusion.
- 96,731 tree components and detections.
- Fusion used a 7 m neighbour radius and a 10 m maximum component spread.
  The spread cap prevents a row of nearby trees from being chained into one
  implausibly large candidate.
- 19,790 fused candidates:
  - 11,182 single-view candidates;
  - 8,608 candidates with two or more views;
  - maximum 19 views;
  - median positional uncertainty 5.996 m;
  - maximum positional uncertainty 10.462 m.
- 6,078 candidates matched a public tree record within 8 m; median matched
  distance **4.99 m**.

Summary: `notes/reports/p67-citywide-summary.json`.

## Off-inventory comparison

LiDAR off-inventory is a separate candidate population, not ground truth. Of the
19,790 street candidates:

- 3,615 are within 5 m of an off-inventory candidate;
- 9,844 are within 10 m;
- 16,753 are within 20 m;
- median nearest distance is **10.05 m**.

This is descriptive overlap only. It does not merge the layers, establish
identity, or claim that a street candidate and a LiDAR candidate are the same
tree.

## Reproducibility

```bash
PYTHONPATH=src:scripts python scripts/street_tree_city.py \
  --dataset /path/to/vancouver_2022 \
  --images-dir /path/to/kartaview-cache \
  --out /path/to/output \
  --max-images 7000 --per-cell 100 --max-workers 32 \
  --batch-size 8 --max-spread 10 --device cuda
```

The run writes `street_tree_detections.json` and the candidate FeatureCollection.
The final layer was re-fused from the cached detections with the 10 m spread cap,
so no second inference pass was needed.

## Preservation

- Canonical full layer: `street_tree_candidates.geojson` (19,790 features).
- P66 1,167-image sample preserved separately as
  `street_tree_candidates_sample1200.geojson`.
- Original 24-candidate Commercial Drive pilot preserved.
- 85-image sparse sample preserved.
- Street candidates remain separate from LiDAR off-inventory and official
  inventory.

## Limits

- Full available **live-host KartaView set reachable through the bounded cell
  scan**, not a complete street census or every historical KartaView record.
- Imagery is predominantly 2016-2018; inventory is current.
- FOV remains assumed at 60° because KartaView generally omits calibration.
- Candidate positions are screening estimates with metre-scale uncertainty.
- No precision, recall, field-validation, survival, ownership, or private-tree
  census claim.
- No Google Street View imagery is used.

## Close-out

- Canonical layer published and served by the public portal.
- Public API and map toggle verified against 19,790 features.
- P67 code changes add batched inference, detection caching, bounded fusion,
  and regression tests.
- PR remains open for approval before merge; no tag or release was created.
