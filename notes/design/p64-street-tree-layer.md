# P64 canonical street-tree layer

Parent issue: #318
Branch: `feature/p64-street-tree-layer`
Status: complete

## Goal

Promote the P63 Vancouver street-level pilot to a canonical, selectable map layer without
merging it into the LiDAR off-inventory or official inventory populations.

## Design

- Canonical data files:
  - `street_tree_candidates.geojson`
  - `street_tree_candidates.json`
- Dataset capability flag: `has_street_trees`.
- API:
  - `GET /api/street-trees` — method, counts, provenance, caveats.
  - `GET /api/street-trees.geojson` — candidate FeatureCollection.
- Map:
  - separate `streetTrees` source;
  - teal `street-tree-candidates` circle layer;
  - independent `street trees` toggle, hidden when the capability is absent;
  - click popup labels the point as a screening candidate, not a confirmed tree.
- No merge with `off_inventory`, official trees, or corrected LiDAR products.

## Out of scope

- New detector or camera calibration.
- Citywide accuracy, precision, survival, ownership, or field-validation claims.
- Google Street View imagery.

## Tasks

- [x] P64.1 Canonical pilot data and API endpoints
- [x] P64.2 Map layer, toggle, and candidate popup
- [ ] P64.3 Tests, browser smoke, docs, PR, and close-out
