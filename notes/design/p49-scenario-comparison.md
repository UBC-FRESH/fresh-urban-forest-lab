# P49 site scenario comparison and assumption presets

Parent issue: #259
Planned branch: `feature/p49-scenario-comparison`
Status: pr-open

## Why

P48 can evaluate one hypothetical site scenario at a time. A user can repeat the work but
cannot keep explicit scenarios, reuse assumptions, or compare them side by side. P49 adds a
bounded local comparison layer.

This is still a **scenario screen**. It is not a ranking, a planting plan, a field-validated
recommendation, or an ownership/access claim.

## Scope

- Save, load, and delete named site scenarios in browser storage.
- Store selected candidate ids, assumptions, evaluation settings, and a cached summary.
- Validate stored/imported scenarios against the current dataset and candidate product.
- Add explicit small/medium/large tree-assumption presets.
- Compare saved evaluated scenarios on sites, trees, baseline/scenario shade, delta, cost,
  and water.
- Export/import a versioned local scenario library with merge-by-name.
- Keep the existing P48 map, 3D handoff, and evaluation API unchanged.

## Out of scope

- Server-backed shared scenarios, accounts, or permissions.
- Automatic ranking or a "best" scenario.
- New optimizer, citywide change claim, survival, cooling, or field validation.
- Ownership, parcel, permit, utility, soil, or access claims.
- Any change to P45's unresolved citywide direction.

## Local scenario contract

Storage key: `fresh.site-scenarios.v1`. Library cap: 20 scenarios.

```json
{
  "version": 1,
  "name": "Eastside medium trees",
  "dataset_id": "vancouver-city-2022",
  "candidates_schema": "fresh-urban-forest.site-candidates.v1",
  "created_at": "2026-11-08T...",
  "selected": ["gap-r21c20-0001", "gap-r20c21-0001"],
  "assumptions": {
    "species": "Acer rubrum",
    "height_m": 8.0,
    "crown_radius_m": 3.0,
    "count": 1,
    "cost_cad": 850.0,
    "water_l_per_year": 1200.0,
    "maintenance": "establishment only"
  },
  "settings": {
    "date": "2026-06-21",
    "time": "12:00",
    "target_height_m": 1.5,
    "sensitivity": false
  },
  "evaluation": {
    "method": "projected-shadow-accumulation-combined",
    "baseline_shade_m2h": 0.0,
    "scenario_shade_m2h": 0.0,
    "delta_shade_m2h": 0.0,
    "delta_shade_pct": 0.0,
    "baseline_shade_fraction": 0.0,
    "scenario_shade_fraction": 0.0
  }
}
```

`evaluation` is an optional cached summary. A scenario without an evaluation can be saved
and loaded but does not appear in the comparison table until evaluated. Scenarios from a
different dataset or candidate schema are rejected rather than applied silently.

## Assumption presets

The presets are clearly labelled scenario assumptions, not species recommendations:

| Preset | Height | Crown radius | Cost/tree | Water/tree/year |
| --- | ---: | ---: | ---: | ---: |
| small | 6 m | 2.0 m | C$650 | 800 L |
| medium | 8 m | 3.0 m | C$850 | 1,200 L |
| large | 12 m | 5.0 m | C$1,400 | 2,000 L |

The user can edit any value after applying a preset. The preset is only a shortcut for a
hypothetical scenario assumption.

## P49.1 Local scenario library, validation, and assumptions

- Add local library save/load/delete.
- Add the three presets and a custom state.
- Validate names, selected ids, assumptions, dataset id, candidate schema, and cached
  evaluation shape.
- Restore selection, assumptions, and settings on load.
- Preserve the existing P48 evaluation and map behavior.
- Add static checks and browser smoke for save/load/delete and preset application.

Acceptance: a saved scenario restores selection and assumptions; malformed records are
rejected; presets are labelled as assumptions; no page errors.

## P49.2 Comparison table and JSON export/import

- Render a comparison table for saved evaluated scenarios.
- Show sites, trees, baseline, scenario, delta, delta percent, cost, and water.
- Keep rows in a stable order; do not rank or call one scenario best.
- Export/import a versioned library with validation and merge-by-name.
- Add browser smoke for import rejection and comparison.

Acceptance: comparison shows only compatible evaluated scenarios; malformed import is
rejected; library is bounded; no ranking or recommendation language.

## P49.3 Browser smoke, docs, and close-out

- Update the site-scenario reference and method report.
- Run dashboard and final browser smoke.
- Open a PR and wait for explicit merge approval.

## Testing plan

- Unit/static checks for library validation and preset values.
- Browser save/load/delete, preset application, malformed import, comparison table.
- Wrong dataset/candidate schema and missing candidate ids.
- No owner/address fields in scenario payloads.
- Dashboard green.

## Risks

- **False authority**: comparison can look like a ranking. Use neutral ordering and explicit
  "hypothetical" labels.
- **Stale evidence**: cached evaluation must carry its dataset/schema and method label.
- **Storage size**: cap the library and store only comparison summaries, not full arrays.
- **Scope creep**: no shared server library or optimizer in this phase.
