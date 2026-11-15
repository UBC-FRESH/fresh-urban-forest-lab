# P65 v0.7.0 release verification

Status: complete. Squash-merged in PR #321 as `abb7961`.

## Metadata

- Package/CITATION/runtime version: **0.7.0**
- Release date: **2026-11-15**
- Release notes: `notes/releases/v0.7.0.md`
- README, project status, and limitations updated through P64.
- Version consistency test: `tests/test_release_metadata.py`

## Verification

- `python scripts/dashboard.py`: **GREEN**
- Release metadata consistency: covered by tests
- Vancouver `has_street_trees=true`; 24 candidate features
- Vancouver toggle visible/enabled; no page errors
- UBC toggle hidden/disabled; no page errors
- Public portal routes remain healthy

## Release actions completed

- Tag `v0.7.0` created from this closeout commit.
- GitHub release published from `notes/releases/v0.7.0.md`.
- Public portal restarted on the release code.
- Vancouver API returned 24 street-tree candidates and the toggle worked.
- All six portal routes returned HTTP 200.

## Limits

- Street candidates are a Commercial Drive pilot, not a citywide inventory.
- FOV is assumed at 60°; imagery is from 2016.
- No field validation, private-tree census, ownership, survival, or accuracy claim.
- No merge with LiDAR off-inventory or official inventory.
