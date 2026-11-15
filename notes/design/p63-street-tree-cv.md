# P63 street-level tree candidate layer

Parent issue: #316
Branch: `feature/p63-street-tree-cv`
Status: pr-open

## Goal

Add an open, reproducible street-level tree candidate layer for Vancouver that is
complementary to, and separate from, the LiDAR off-inventory layer.

## Data and licence

- KartaView public imagery is the first provider: CC BY-SA 4.0, attribution to Grab and
  KartaView contributors, no token required for the pilot.
- Mapillary can be added later with a user token; Google Street View is not part of the
  open default because it is proprietary and redistribution-restricted.
- OneFormer ADE20K is MIT; ZoeDepth is MIT.
- Public Vancouver tree records are used only for descriptive matching, not as complete
  ground truth.

## Design

- `street_trees.py` provides the provider contract, camera projection, candidate fusion,
  inventory matching, and GeoJSON output.
- The street-level layer uses `source=street_level_cv`, `not_ground_truth=true`, and a
  separate candidate file.
- It does not merge with `off_inventory.geojson`, the official inventory, or corrected
  LiDAR products.
- The operator pilot in `scripts/street_tree_pilot.py` uses OneFormer semantic tree masks,
  distance-peak instance splitting, and ZoeDepth metric depth.
- The first pilot assumes a 60° horizontal FOV because KartaView generally omits camera
  calibration; this must remain explicit.

## Out of scope

- Google Street View imagery/API keys in the public package.
- A field-validated or complete private-tree census.
- A citywide detection-rate claim from one corridor.
- UI integration until the pilot has usable metrics.

## Tasks

- [x] P63.1 Literature/provider/model feasibility and design
- [x] P63.2 Core street-tree geometry, provider, fusion, and tests
- [x] P63.3 Vancouver corridor pilot and inventory comparison
- [ ] P63.4 Docs, PR, and close-out
