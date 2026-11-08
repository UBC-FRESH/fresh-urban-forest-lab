# P48 site-level planting scenarios

Status: implementation complete; close-out pending.

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

## P48.2 Site-level shade simulation and scenario metrics

The evaluator reuses the existing projected-shadow accumulation model. Baseline and
scenario use the same samples, target height, step, and terrain setting. The scenario adds
hypothetical trees at the selected candidate sites using explicit species, height, crown
radius, and count. It reports combined shade area-hours, shade fractions, percent deltas,
per-site contributions, and optional height/crown sensitivity cases.

Vancouver two-site pilot:

- Baseline dataset: 29,096 trees; 862 by 633 terrain grid.
- Sample: 2026-06-21 12:00 PDT; target height 1.5 m; two `plant + cool` sites.
- Assumption: 8 m height, 3 m crown radius, one tree per site.
- Baseline: **35,752,669.3 m²h** combined shade area-hours.
- Scenario: **35,753,827.6 m²h**; delta **+1,158.34 m²h** (**+0.0032%**).
- Per-site deltas: **+579.17 m²h** each.
- Height/crown ±20% sensitivity range: **+868.75 to +1,737.51 m²h**.
- This is one time sample, not annual shade. Sensitivity is a model/geometry response,
  not a biological growth or survival forecast.

The output labels the method as `projected-shadow-accumulation-combined` and records:
`scenario screen, not observed shade`; P45 citywide change remains unresolved.

## P48.3 Scenario API, map, and 3D comparison

The Sites tab loads the optional candidate GeoJSON, colours candidate points by action,
and lets a user click sites on or off. A six-site quick-select chooses `plant + cool` sites.
The panel applies shared species, height, crown radius, tree count, cost, water, and
maintenance assumptions to every selected site.

API:

- `GET /api/site-candidates`
- `GET /api/site-candidates.geojson`
- `POST /api/site-scenario/evaluate`

The evaluation endpoint validates the scenario and candidate ids, parses ISO sample times,
and returns the normalized scenario plus baseline/scenario shade, per-site contributions,
and optional sensitivity.

Browser smoke:

- 5,000 candidate points loaded on the Sites map.
- Six `plant + cool` sites selected.
- Sample: 2026-06-21 12:00 Vancouver local time; target height 1.5 m.
- Baseline 35.8M m²h; scenario delta **+3.5k m²h (+0.0097%)**.
- Per-site deltas ranged **+290 to +869 m²h**.
- **Open in 3D** created a normal scenario with six hypothetical trees and switched to the
  existing 3D scene without page errors.

Limits remain: this is an above-ground candidate screen and hypothetical scenario, not a
planting plan, ownership or access check, survival forecast, or field validation.

## P48.4 verification and limits

- Dashboard gates green.
- Final browser smoke: 5,000 candidates loaded; six `plant + cool` sites selected;
  sensitivity enabled; baseline 35.8M m²h and delta +3.5k m²h (+0.0097%); 10 result rows
  across per-site and sensitivity tables; clear and re-select worked; 3D handoff reached
  the scene; no page errors.
- Documentation: `docs/reference/site-scenarios.rst`.
- P48 is a scenario screen. Candidate sites are not parcels or permission; shade is a
  projected model result; P45's citywide change direction is unresolved.
- No accounts, ownership, survival, field validation, or planting-plan claim is added.
