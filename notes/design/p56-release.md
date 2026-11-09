# P56 v0.4.0 release and portal verification

Parent issue: #299
Branch: `release/v0.4.0`
Status: active

## Goal

Freeze the corrected public urban-forest product, document the P30–P55 state, audit the
five public demo portals and their visible controls, and prepare v0.4.0 for explicit release
approval.

## Scope

- Update `pyproject.toml`, `CITATION.cff`, README status, and docs project status.
- Add `notes/releases/v0.4.0.md`.
- Audit all five routes and visible map controls.
- Verify hidden/disabled controls when a dataset lacks a product.
- Run dashboard, docs, CI, and browser smoke.
- Open a release PR. Do not tag or publish without explicit approval.

## Out of scope

- New science, new features, or field validation.
- Unapproved tag/GitHub release changes.
- Silent replacement of original P43/P44/P46 lineage.

## Release content

- P30 full Vancouver city pilot.
- P38–P46 shade/equity, gaps, heat, change, action, turnover.
- P47–P50 optimization explorer and site scenarios.
- P51–P55 full-city vertical control, corrected products, and outlier adjudication.
- P54/P55 corrected action/turnover publication.

## Verification

- `python scripts/dashboard.py`
- `python scripts/check_workflow.py`
- browser smoke of `/ubc/`, `/vancouver/`, `/surrey/`, `/burnaby/`, `/coquitlam/`
- visible toggle audit; no dead controls
- clean deployment check at `:8101`

## Approval gate

A maintainer must explicitly approve before:
- creating/pushing tag `v0.4.0`;
- publishing the GitHub release;
- any deployment/settings change beyond the release code PR.
