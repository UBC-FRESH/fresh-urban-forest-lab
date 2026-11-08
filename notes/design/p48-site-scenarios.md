# P48 site-level planting scenarios

Parent issue: #247
Planned branch: `feature/p48-site-scenarios`
Status: pr-open

## Why

P39 screens above-ground gap area and P42/P44 label 400 m cells for canopy action.
Neither product is a planting plan. P48 adds a bounded scenario layer so a user can place a
small number of hypothetical trees at candidate sites and see the consequences under
explicit assumptions.

The output is a **scenario**, not a recommendation. Ownership, access, utilities, soil,
permits, survival, and maintenance remain unknown.

## Scope

- Derive candidate planting sites from P39 gap components and P42/P44 action cells.
- Keep the official public-tree inventory separate from LiDAR-derived candidates.
- Place hypothetical trees with explicit species, height, crown-radius, cost, water, and
  maintenance assumptions.
- Compare baseline and scenario shade with the existing shadow/shade model or a clearly
  labelled deterministic proxy.
- Show site-level and scenario-level totals with evidence tiers and uncertainty.
- Reuse P47 saved-view and parallel-coordinate patterns where they add value.
- Preserve P45's warning that the citywide change direction is unresolved.

## Out of scope

- Ownership, parcel, permit, access, or utility claims.
- A private-tree census or confirmed planting locations.
- Tree survival, species identification, or causal attribution.
- A new optimizer, citywide net-change claim, or operational recommendation.
- Field validation, budgeting commitments, or a claim that a scenario is approved.

## Candidate sites

P39 currently publishes 400 m aggregates and component counts, not individual component
geometries. P48.1 will either:

1. extend the P39 build to emit component geometries with stable ids; or
2. recompute contiguous components from the P39 masks with the same thresholds.

Each candidate site must carry:

```json
{
  "site_id": "gap-r00c14-0001",
  "cell_id": "r00c14",
  "source": "p39_edge_gap",
  "lon": -123.14,
  "lat": 49.29,
  "area_m2": 67.2,
  "street_adjacent": true,
  "action_label": "plant_cool",
  "evidence_tier": "candidate",
  "notes": ["above-ground screen; ownership/access unknown"]
}
```

The candidate layer is not a property layer and must not include owner names, addresses, or
parcel-level ownership assertions.

## Scenario contract

```json
{
  "schema_version": "fresh-urban-forest.site-scenario.v1",
  "scenario_id": "scenario-...",
  "label": "Downtown shade pilot",
  "created_at": "2026-11-08T...",
  "baseline": {
    "dataset_id": "vancouver-city-2022",
    "shade_method": "existing-shadow-model",
    "assumptions": {}
  },
  "sites": [
    {
      "site_id": "gap-r00c14-0001",
      "species": "Acer rubrum",
      "height_m": 6.0,
      "crown_radius_m": 2.5,
      "count": 1,
      "cost_cad": 850,
      "water_l_per_year": 1200,
      "maintenance": "establishment only",
      "assumption_source": "explicit scenario input"
    }
  ],
  "totals": {
    "sites": 12,
    "trees": 12,
    "cost_cad": 10200,
    "water_l_per_year": 14400
  },
  "metrics": {
    "baseline_shade_m2h": 0.0,
    "scenario_shade_m2h": 0.0,
    "delta_shade_m2h": 0.0,
    "delta_shade_pct": 0.0
  },
  "uncertainty": {
    "shade_model": "proxy or model label",
    "height_sensitivity": [],
    "caveats": []
  }
}
```

All numeric outputs must state their method. A scenario total is not an observed outcome.

## P48.1 Candidate-site and scenario data contract

- Extend or reuse the P39 gap build to emit candidate component points.
- Join P42/P44 action labels without treating them as planting permission.
- Add a validated scenario schema, stable ids, and a bounded site count.
- Add unit tests for component extraction, joins, validation, bounds, and empty cases.
- Keep candidate sites separate from the public-tree inventory in API and UI.

Acceptance: a deterministic candidate-site file exists with documented thresholds; scenario
round-trips through JSON; invalid/oversized payloads are rejected; no ownership fields.

## P48.2 Site-level shade simulation and scenario metrics

- Reuse `fresh_urban_forest.shadow` / `shade` where practical.
- If a full daily simulation is too costly, use a deterministic local shadow proxy and
  label it clearly.
- Compute baseline and scenario shade for the selected sites and time window.
- Report per-site and total deltas, plus height/crown sensitivity.
- Keep cost, water, and maintenance assumptions separate from biophysical outputs.

Acceptance: baseline and scenario are computed from the same time/geometry settings; the
method label is visible; numbers are reproducible; P45's unresolved citywide direction is
not contradicted.

## P48.3 Scenario API, map/3D UI, and comparison

- Add API routes for candidate sites and scenario evaluation.
- Add a site layer and scenario panel without overloading the Optimize tab.
- Let a user select a bounded set of sites, set species/height/crown/cost/water assumptions,
  and evaluate the scenario.
- Show baseline versus scenario shade, assumptions, evidence tier, and caveats.
- Reuse P47 patterns for saved scenario state where they fit; do not fork another explorer.
- Provide a clear empty state and no-action state.

Acceptance: selecting sites produces a scenario; assumptions are editable and visible;
baseline/scenario comparison works; invalid or empty scenarios are explicit; mobile and
keyboard basics remain usable.

## P48.4 Validation, browser smoke, docs, and close-out

- Unit/API tests, deterministic fixture tests, and browser smoke.
- Document method, inputs, assumptions, limits, and evidence tiers.
- Add a phase report and update `ROADMAP.md`/`CHANGE_LOG.md`.
- Run dashboard and CI; open PR; wait for explicit merge approval.

Acceptance: dashboard green; browser smoke has no page errors; docs state the scenario is
not a planting plan; PR is reviewed before merge.

## Testing plan

- Component extraction and site-id stability.
- Scenario schema validation: missing fields, bad ranges, duplicate ids, oversized lists.
- Join behavior for P39/P42 labels and missing products.
- Shade baseline/scenario determinism and sensitivity.
- API round-trip and malformed payloads.
- Browser: site load, select, edit assumptions, evaluate, compare, empty/invalid states.
- No owner/address fields in candidate or scenario payloads.

## Risks

- **False precision**: a small scenario can look more certain than its inputs.
- **Site geometry**: P39 components are not ownership or access evidence.
- **Shade model cost**: full simulation may be expensive; label any proxy.
- **Scope creep**: scenario builder can drift into a planting plan or optimizer.
- **P45**: do not present scenario shade as a citywide change signal.
