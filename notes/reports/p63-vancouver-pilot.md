# P63 street-level tree candidate pilot

Status: implementation complete; PR review pending.

## What this is

An open, credential-free street-level tree candidate pipeline for Vancouver, separate from
both the official inventory and the LiDAR-derived off-inventory layer.

The pilot follows the Lumnitz approach conceptually: detect tree instances in street-level
imagery, estimate camera-to-tree distance, project each detection to a geographic position,
and fuse multiple views. It is a modern open analogue, not a copy of the original code or
weights.

## Sources and models

- **Imagery:** KartaView public API, CC BY-SA 4.0, attribution © Grab and KartaView
  contributors. No token is required for the pilot.
- **Segmentation:** `shi-labs/oneformer_ade20k_swin_tiny`, MIT.
- **Depth:** `Intel/zoedepth-nyu-kitti`, MIT.
- **Inventory matching:** City of Vancouver public tree records, OGL-Vancouver. The
  inventory is incomplete for private trees.

Google Street View and Mapillary are not used in this pilot. Google imagery is proprietary;
Mapillary would require an access token.

## Pilot result

Query: Commercial Drive area, `49.255 N, -123.070 W`, 500 m radius.

- 70 KartaView metadata records returned; 8 images decoded successfully.
- Several older CDN image URLs returned HTTP 500 and were skipped.
- 8 images produced 75 tree components and 29 fused candidates.
- 6 candidates matched a public tree within 8 m; median matched distance **5.41 m**.
- Camera FOV was not supplied by KartaView, so a documented **60°** default was used.
- Imagery is from 2016; the inventory is current. This is a temporal mismatch.
- No detection-rate or precision claim is made. The public inventory cannot identify
  private-tree false positives.

Summary: `notes/reports/p63-pilot-summary.json`.

## Complementarity with LiDAR off-inventory

- Street candidates use `source=street_level_cv` and `not_ground_truth=true`.
- They are written to a separate `street_tree_candidates.geojson` layer.
- They are never merged into `off_inventory.geojson`, the official inventory, or the
  corrected LiDAR products.
- A future comparison may report overlap between the two candidate populations, but they
  answer different questions: street-level visibility versus ALS canopy structure.

## Limits

- FOV is assumed for KartaView images; positional error is not independently calibrated.
- OneFormer is a semantic segmenter; watershed splitting is a heuristic for dense crowns.
- The 60° assumption and 2016 imagery make the pilot unsuitable for a change or survival
  claim.
- No field validation, private-tree census, ownership, or citywide claim.
- The pilot is one corridor, not a representative city sample.

## Reproduce

```bash
python -m pip install -e ".[street]"
PYTHONPATH=src python scripts/street_tree_pilot.py \
  --lat 49.2550 --lon -123.0700 --radius 500 --limit 8 \
  --dataset data/processed/vancouver_2022 \
  --images-dir data/external/street_trees/images \
  --out data/processed/street_trees_pilot
```

The first run downloads model weights and optional dependencies. Raw KartaView images and
pilot outputs stay outside git.
