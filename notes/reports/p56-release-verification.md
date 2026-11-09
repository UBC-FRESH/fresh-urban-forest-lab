# P56 v0.4.0 release verification

Status: release candidate verified; tag/GitHub release pending approval.

## Metadata

- Package/CITATION version: **0.4.0**
- Release date: **2026-11-09**
- Release notes: `notes/releases/v0.4.0.md`
- README and project status updated through P55.

## Portal audit

Public portal: `:8101`

All five routes returned HTTP 200:

- `/ubc/`
- `/vancouver/`
- `/surrey/`
- `/burnaby/`
- `/coquitlam/`

Browser audit:

- all visible tabs opened in every demo
- no page errors
- no visible map toggle lacked its dataset product
- unavailable layer toggles are hidden

Vancouver specifically:

- action/turnover default to corrected versions
- original versions remain selectable
- Change tab defaults to `change_control.json`
- shade equity, canopy gaps, and heat equity layers change the map
- corrected change: **−94 ha / +0.52 m**
- original change: **+223 ha / +1.48 m**

## Gates

- Dashboard: **GREEN** — lint, format, types, tests, validator, docs
- Workflow validator: **GREEN**
- Docs build: **GREEN**
- CI on release PR: pending

## Release boundary

The release PR may be merged after approval. The following still require explicit approval:

- creating/pushing tag `v0.4.0`
- publishing the GitHub release
- any deployment/settings change beyond the release code

## Limits

- Four western control outliers remain documented.
- No field validation or survey-grade claim.
- Corrected products are full-control screens, not final citywide net-loss claims.
- P32 second reviewer and P37 remain separate.
