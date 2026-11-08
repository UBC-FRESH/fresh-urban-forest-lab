# P54 corrected action and turnover publication

Status: implementation complete; PR review pending.

## API

Optional versioned endpoints:

- `/api/canopy-action?version=original|control`
- `/api/canopy-action.geojson?version=original|control`
- `/api/canopy-turnover?version=original|control`
- `/api/canopy-turnover.geojson?version=original|control`

The API default remains `original` for backward compatibility. Corrected sidecars are
advertised through `has_canopy_action_control` and `has_canopy_turnover_control`.

## UI

- Action and turnover panels have version selectors.
- The corrected version is selected by default when present.
- The original version remains selectable.
- Change tab prefers `change_control.json` when present.
- Status reads `full-control` or `original`.

## Counts

P44:

| Action | Original | Corrected |
| --- | ---: | ---: |
| plant + cool | 50 | 162 |
| monitor | 101 | 195 |
| expand canopy | 77 | 110 |
| structural shade | 23 | 113 |
| protect / investigate loss | 546 | 217 |

P46:

- high-tier cells: 260 original / 260 corrected
- turnover area: 181.76 ha original / 135.64 ha corrected

## Browser smoke

- Defaults: action/turnover `control`; Change `change_control.json`
- Corrected action counts loaded; corrected turnover 260 high / 135.64 ha
- Switching to original restored 50/101/77/23/546 and 181.76 ha
- Change tab: corrected −94 ha / +0.52 m; original +223 ha / +1.48 m
- No page errors

## Limits

- Corrected products remain a full-control screen, not a final citywide net-loss claim.
- The original API default is preserved; no silent replacement.
- No field validation, survival, ownership, or planting claim.
