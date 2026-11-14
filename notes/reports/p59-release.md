# P59 v0.5.0 release verification

Status: release candidate; merge, tag, and publication pending approval.

## Metadata

- Package/CITATION/runtime version: **0.5.0**
- Release date: **2026-11-14**
- Release notes: `notes/releases/v0.5.0.md`
- README and project-status docs updated through P58
- Version consistency test: `tests/test_release_metadata.py`

## Verification

- `python scripts/dashboard.py`: **GREEN** — lint, format, types, tests, validator, docs
- Workflow validator: **GREEN**
- Docs build: **GREEN**
- UBC browser smoke:
  - 3D scene opened
  - Walk mode entered
  - pointer lock captured
  - HUD appeared
  - `W` was accepted
  - Orbit restored and HUD hid
  - no page errors

## Release boundary

The release PR may be merged after approval. Still required:

- tag `v0.5.0`
- GitHub release
- public portal restart on the release code

## Limits

- No scientific product, data claim, default layer, or corrected-product threshold changed.
- Walk mode is in-engine navigation, not Google Street View imagery.
- No building interiors or complete physical collision.
- Four western vertical-control outliers and the P32 review gap remain documented.
