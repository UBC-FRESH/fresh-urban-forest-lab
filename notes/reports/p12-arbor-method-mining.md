# P12 close-out: Arbor method mining and clean-room point-cloud primitives

Phase: P12 Arbor method mining and clean-room point-cloud primitives
Parent issue: #61
Pull request: #63, `feature/p12-arbor-methods` into `main`
Evidence head: `ff8da4f`
Report commit: the commit that adds this report
Date: 2026-11-03
Status: approved; merge and close-out in progress

## Recommendation

Approve these actions. The agent carries them out in this order and reads back each result.

1. Squash-merge pull request #63 and delete `feature/p12-arbor-methods`.
2. Close parent issue #61 and child issue #62 with a closeout comment that cites the merge
   commit.
3. Launch P13: ALS ground classification and height above ground, in
   `fresh-urban-forest-lab` first, with real LidarBC-tile validation before any move to
   FEMIC.

Settings changes: none.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Arbor source snapshot and licence boundary recorded | `notes/reference/arbor-method-mining.md`; ADR 0006 | met |
| Candidate matrix, design patterns, and attribution templates recorded | same note, sections 3-7 | met |
| Four opt-in point-cloud primitives implemented | `src/fresh_urban_forest/pointcloud.py` | met |
| Public functions have NumPy-style docstrings with `Method provenance` | module docstrings; Sphinx API page | met |
| Synthetic tests cover nominal, edge, determinism, and invalid inputs | `tests/test_pointcloud.py`; 19 tests | met |
| No Arbor source code copied and no GPL code added | no Arbor imports or vendored files; ADR 0006 | met |
| Dashboard green | `python scripts/dashboard.py`; CI run 41742328362 | met |
| PR open and CI green | PR #63; three checks pass | met |

## 2. Workflow compliance

- Parent issue before the branch: #61 created before #62 and before
  `feature/p12-arbor-methods`.
- Child issue before implementation: #62 created before the branch.
- Branch from `main`: worktree branch created from `origin/main` at `2dd72b5`.
- Commit messages start with task IDs: `P12.1 add Arbor provenance and point-cloud
  primitives` (`ff8da4f`).
- Roadmap and changelog in step: both changed in `ff8da4f`; the close-out report and status
  update are in the report commit.
- Child issue closeout: pending this report and the merge.
- Approval gates: user said "go" after the PR summary; no tag, release, settings change, or
  merge happened before this report.

## 3. Gate evidence

`python scripts/dashboard.py` at `ff8da4f`:

- lint: GREEN
- format: GREEN
- types: GREEN
- tests: GREEN
- validator: GREEN
- docs: GREEN

`python -m pytest -q` at `ff8da4f`: 287 passed, total coverage 87.51 percent. The new
`pointcloud.py` module is 92 percent covered.

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 41742328362 | `ff8da4f` | success | Quality gates, Pre-commit parity, and Green dashboard summary all pass |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| No deviations from the P12.1 scope | The four functions are opt-in and are not wired into the default CHM/ITD path | Recorded in the changelog and note |

## 6. Next phase

P13 should add ALS ground classification and HAG to the point-cloud lane, starting in
`fresh-urban-forest-lab` so it can reuse the new `pointcloud.py` surface and the existing
`laspy` ingestion. Move or adapt it to FEMIC only after a real LidarBC tile passes the same
acceptance evidence.

Recommended tasks:

- P13.1: PTD algorithm specification, synthetic terrain fixtures, and a bounded input
  contract.
- P13.2: Python PTD ground classification and TIN-based HAG with a QA report.
- P13.3: Validation on a real LidarBC/ALS tile, including low-point cut, ground class
  counts, and HAG sanity checks.
- P13.4: Optional integration into the CHM/ITD preprocessing path and docs.

Acceptance for P13:

- A flat plane, a sloped plane, and a scene with a building/tree outlier classify the
  expected ground points.
- HAG is zero-mean on synthetic ground and positive on vegetation.
- A real LidarBC tile reports ground points, HAG percentiles, and a QA warning count.
- The implementation cites Axelsson (2000), the Arbor book chapter 4, and Arbor's PTD
  vendor note; no GPL code is copied.
- The dashboard is green.

## 7. Decision

- [x] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
