# P49 site scenario comparison

Status: implementation complete; close-out pending.

## P49.1 Local scenario library and assumption presets

The Sites tab now has a browser-local library capped at 20 named scenarios. Each record
stores selected candidate ids, species/height/crown/count/cost/water/maintenance
assumptions, date/time/target-height settings, the dataset id, candidate schema, and an
optional cached shade summary.

Validation rejects malformed records, duplicate candidate ids, out-of-range assumptions,
wrong datasets or candidate schemas, and missing candidates. Scenarios are not silently
applied across incompatible products.

Three presets provide explicit shortcuts only:

| Preset | Height | Crown radius | Cost/tree | Water/tree/year |
| --- | ---: | ---: | ---: | ---: |
| small | 6 m | 2.0 m | C$650 | 800 L |
| medium | 8 m | 3.0 m | C$850 | 1,200 L |
| large | 12 m | 5.0 m | C$1,400 | 2,000 L |

The user can edit any value after applying a preset. These are hypothetical scenario
assumptions, not species recommendations.

Browser smoke: medium preset applied 8 m / 3 m / C$850 / 1,200 L; a six-site scenario was
saved; changing preset and clearing selection then loading restored six sites and the
medium assumptions; delete removed the record; no page errors.

No ranking, planting-plan, ownership, survival, field-validation, or citywide-change claim is added.

## P49.2 Comparison table and JSON portability

The saved-scenario panel now includes a neutral comparison table for evaluated scenarios
compatible with the current dataset and candidate schema. It shows scenario name, sites,
trees, baseline, scenario, delta, delta percent, cost, and water. Rows are sorted by name;
there is no ranking or recommendation language.

JSON export contains `{version, exported_at, scenarios}`. Import validates the version and
every record, merges by name, caps the library at 20, and rejects malformed payloads.

Browser smoke: two evaluated scenarios were saved; both appeared in the comparison table;
export contained both; deleting them cleared the table; importing the export restored both;
a malformed record was rejected. No page errors.

## P49.3 Verification and close-out

- Final browser smoke: 5,000 candidates loaded; medium preset applied; six-site scenario
  evaluated; two saved scenarios compared; export/import round-trip; 3D handoff; no page
  errors.
- Documentation updated in `docs/reference/site-scenarios.rst`.
- Dashboard gates green.
- P49 remains a neutral local comparison tool. It does not rank scenarios or make a
  planting-plan, ownership, survival, field-validation, or citywide-change claim.
