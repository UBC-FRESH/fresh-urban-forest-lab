# P49 site scenario comparison

Status: active.

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

Comparison table and JSON export/import remain for P49.2. No ranking, planting-plan,
ownership, survival, field-validation, or citywide-change claim is added.
