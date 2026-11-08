# P48 site-level planting scenarios

Status: active.

## P48.1 Candidate-site and scenario data contract

The candidate layer extracts contiguous P39 gap components, keeps the largest components
within the deterministic per-cell and global caps, and joins P42/P44 action labels as
context only. Candidate records contain no owner, address, parcel, or permit fields.

The scenario contract is `fresh-urban-forest.site-scenario.v1`. It bounds scenario sites
(200), trees (1,000), and per-site assumptions; derives site/tree/cost/water totals; and can
validate site ids against a candidate set.

Vancouver candidate build:

- 5,000 candidate sites at the configured cap; 12 per cell.
- Action context: expand 906, plant 588, protect/investigate 3,243, structural 263.
- Outputs under `data/processed/vancouver_2022/`: `site_candidates.json`,
  `site_candidates.geojson`, `site_candidates_meta.json`.

Limits: candidate sites are open-ground components, not parcels or planting permissions.
No ownership, access, utility, soil, irrigation, maintenance, survival, or field-validation
claim is made. P48.2 still has to define and label the shade evaluation.
