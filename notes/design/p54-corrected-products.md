# P54 corrected action and turnover product publication

Parent issue: #288
Planned branch: `feature/p54-corrected-products`
Status: active

## Why

P53 published the full-control corrected P43 change layer as a selectable sidecar, but the
P44 action and P46 turnover panels still consume the original P43 lineage. P54 exposes the
corrected P44/P46 sidecars and makes the app's version choice explicit.

## Scope

- Add optional `version=original|control` support to action and turnover API endpoints.
- Publish corrected sidecars under the runtime dataset:
  - `canopy_action_control.json/.geojson`
  - `canopy_turnover_control.json/.geojson`
- Add version selectors to the action and turnover panels.
- Default to `control` when available; keep `original` selectable.
- Update map sources and summaries on version changes.
- Label the corrected version as full 181-tile ground-control corrected and non-final.
- Add docs, API/UI tests, browser smoke, and close-out.

## Out of scope

- New control data collection.
- Silent replacement of original products.
- Final citywide net-loss claim, field validation, survival, ownership, or planting claims.

## API

`GET /api/canopy-action?version=original|control`
`GET /api/canopy-action.geojson?version=original|control`
`GET /api/canopy-turnover?version=original|control`
`GET /api/canopy-turnover.geojson?version=original|control`

The original endpoints remain backward-compatible with the default `original` version.
Dataset flags advertise corrected sidecars.

## UI

- Action panel: version selector, default `control` when available.
- Turnover panel: version selector, default `control` when available.
- Change tab: prefer `change_control.json` when present.
- Status/summary labels name the selected version.
- Original versions remain selectable.

## Acceptance

- Original and corrected versions both load through the API.
- UI switches map, summary, and labels without page errors.
- Corrected version is default only when present, with an explicit label.
- Original products remain available.
- No unsupported claim is added.
- Dashboard green.
