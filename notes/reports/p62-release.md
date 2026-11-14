# P62 v0.6.0 release verification

Status: complete. Squash-merged in PR #315 as `7ad143a`.

## Metadata

- Package/CITATION/runtime version: **0.6.0**
- Release date: **2026-11-14**
- Release notes: `notes/releases/v0.6.0.md`
- README, project status, and limitations updated through P61
- Version consistency test: `tests/test_release_metadata.py`

## Verification

- `python scripts/dashboard.py`: **GREEN** — lint, format, types, tests, validator, docs
- Workflow validator: **GREEN**
- Docs build: **GREEN**
- UBC browser smoke: Street spawn, collision grid, HUD, minimap, coordinates, movement
- Vancouver browser smoke: Street spawn and HUD, no page errors
- Public portal routes remain healthy

## Release actions completed

- Tag `v0.6.0` created from this closeout commit.
- GitHub release published from `notes/releases/v0.6.0.md`.
- Public portal restarted on the release code from `main-worktree`.
- Portal routes `/`, `/ubc/`, `/vancouver/`, `/surrey/`, `/burnaby/`, and `/coquitlam/`
  returned HTTP 200.
- Deployed UBC Walk v2 smoke passed with no page errors.

## Limits

- No scientific product, data claim, default layer, or corrected-product threshold changed.
- No building interiors, stairs, doors, full physics, or tree collision.
- Not Google Street View imagery.
- Headless full-city street rendering is slow; hardware-GPU performance remains untested.
- Four western vertical-control outliers and the P32 review gap remain documented.
