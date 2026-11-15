# P65 v0.7.0 release verification

Status: release candidate; merge, tag, and publication pending approval.

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

## Release boundary

The release PR may be merged after approval. Still required:

- tag `v0.7.0`
- GitHub release
- public portal restart on the release code

## Limits

- Street candidates are a Commercial Drive pilot, not a citywide inventory.
- FOV is assumed at 60°; imagery is from 2016.
- No field validation, private-tree census, ownership, survival, or accuracy claim.
- No merge with LiDAR off-inventory or official inventory.
