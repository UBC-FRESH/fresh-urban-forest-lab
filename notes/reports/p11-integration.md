# P11 close-out: integration and v0.3 release candidate

Date: 2026-11-04
Phase: P11
Parent issue: #44
Branch: `feature/p11-integration`
Implementation head: pending at report write; refreshed at PR queue
Status: ready for review

## Summary

P11 composes the P7-P10 layers into one portable lab report, adds the report export to the
browser, and prepares the v0.3.0 release candidate.

No tag or GitHub release has been created.

## Acceptance evidence

| Criterion | Status | Evidence |
| --- | --- | --- |
| One scenario reports shade, water, cost, birds, and a Pareto archive | met with limit | unified report composes metrics, shade, birds, off-inventory; water/cost remain in scenario/irrigation cards; Pareto archive is linked through the Optimize tab, not embedded in every report |
| Clean clone reproduces the benchmark from a manifest | met with limit | benchmark commands and evidence JSON recorded; no CI clean-clone job yet |
| Docs describe every method and limit | met | new integration page plus P7-P10 docs |
| Release candidate queued; no tag without approval | met | version 0.3.0 and release notes; no tag |

## What was implemented

- `integration.py`: `build_lab_report` and `write_lab_report`.
- Unified JSON report with:
  - dataset summary and provenance;
  - scenario id/name/year;
  - metrics and completeness;
  - representative-day shade;
  - bird habitat/guilds/demography;
  - off-inventory summary;
  - evidence list and caveats.
- `GET /api/report?scenario_id=&year=`.
- `fresh-urban-forest report`.
- **Export lab report** button in the scenario panel.
- Version metadata 0.3.0.
- `docs/reference/integration-and-release.rst`.
- `notes/releases/v0.3.0.md`.

## Verification

- Dashboard GREEN.
- Browser check: report button downloads a JSON bundle; no console/page errors.
- Report composition is deterministic and JSON-safe.
- Existing P8 benchmark evidence remains:
  - 387 sites, 72 scalarizations, 1,010,952 evaluations
  - 71 archive solutions, hypervolume 0.0508
  - 100.94 s on 8 workers
- Z* convergence evidence remains:
  - 112,116 evaluations, 36 rounds, patience stop
  - best balanced objective -0.293285

## What was not integrated

- The Pareto archive is not embedded in the JSON report; it remains a separate saved
  archive linked from the Optimize tab.
- Water/irrigation remains on the tree card and water API, not a single scenario total in
  the report.
- No clean-clone CI job yet; the report records the commands but does not execute them in a
  fresh container.

These are stated limits, not hidden behavior.

## Release candidate

- Version: `0.3.0`
- Release notes: `notes/releases/v0.3.0.md`
- No tag, release, Pages setting change, or public deployment has been performed.
- Release actions require explicit maintainer approval.

## Known gaps

- Field validation remains incomplete.
- Bird demography is prior-driven.
- Off-inventory ownership is unknown.
- Optimization is a finite scalarisation approximation.
- City LiDAR coverage is two core tiles.
- The unified report is a composition, not a new calibrated model.

## Next phase

Phase 6 (operate and maintain) is the next lifecycle stage. The v0.3 release candidate
needs maintainer approval before a tag or release.
