# P64 canonical street-tree layer verification

Status: complete. Squash-merged in PR #319 as `9b547e4`.

## Data

The Vancouver pilot output is published as:

- `street_tree_candidates.geojson`: 24 candidates.
- `street_tree_candidates.json`: method, counts, provenance, and caveats.

The files stay in the generated dataset, not in git. The dataset advertises
`has_street_trees`.

## API

- `GET /api/street-trees` returns the summary.
- `GET /api/street-trees.geojson` returns the FeatureCollection.
- Both return 404 when the dataset has no street-tree layer.

## Map

- Separate teal source/layer, distinct from the orange LiDAR off-inventory layer.
- Independent `street trees` toggle.
- Toggle is hidden and disabled when `has_street_trees` is false.
- Clicking a candidate opens a popup with view count, positional uncertainty, and
  “screening point, not a confirmed tree.”
- No merge with the official inventory or off-inventory candidate records.

## Verification

- Dashboard: **GREEN** — lint, format, types, tests, validator, docs.
- Service contract tested for optional 404, summary, GeoJSON, and dataset capability.
- Vancouver browser smoke: toggle visible, enabled, and can be checked; no page errors.
- UBC browser smoke: toggle hidden and disabled; no page errors.
- Canonical Vancouver API returned 24 features.
- No scientific product or default layer changed beyond the new optional layer.

## Limits

- The layer is a pilot corridor around Commercial Drive, not a citywide inventory.
- FOV remains an assumed 60°.
- Imagery is 2016 and the public inventory is current.
- Candidate positions and detections are screening results, not field facts.
- The public inventory cannot identify private-tree false positives.

## Close-out

- PR #319 squash-merged into `main` as `9b547e4`.
- Public portal restarted on the new code; Vancouver `has_street_trees=true`, 24 features.
- Vancouver browser smoke: toggle visible/enabled and checked with no page errors.
- UBC browser smoke: toggle hidden/disabled with no page errors.
- Dashboard: **GREEN**.
