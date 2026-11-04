# P13 close-out: ALS ground classification and height above ground

Phase: P13 ALS ground classification and height above ground
Parent issue: #70
Pull request: #72, `feature/p13-als-ground` into `main`
Evidence head: `1bc56fb`
Report commit: the commit that adds this report
Date: 2026-11-04
Status: approved; merge and close-out in progress

## Recommendation

Approve these actions. The agent carries them out in this order and reads back each result.

1. Squash-merge pull request #72 and delete `feature/p13-als-ground`.
2. Close parent issue #70 and child issues #71, #80, #82, and #87 with a closeout comment
   that cites the merge commit.
3. Do not launch a new implementation phase automatically. Recommend P14: a checked ground
   reference patch and a second terrain type before any FEMIC integration.

Settings changes: none.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| PTD-inspired ground classifier and HAG | `classify_ground_ptd`, `GroundClassification` | met |
| Synthetic flat, slope, outlier, degenerate-TIN, empty, and invalid-parameter tests | `tests/test_pointcloud.py`; 27 point-cloud tests | met |
| Real LidarBC tile validation | 415,068-point 2025 tile; class-2 recall 0.9998; HAG p99 0.021 m | met with limit |
| Reference classes treated honestly | report states class 1/7 are not negatives; precision not claimed | met |
| SOR/low-point policy | SOR on two tiles; `low_point_mask(0.15)`; class-7 HAG evidence | met |
| FEMIC integration decision | P13.4 defers until reference patch and second terrain type | met |
| No GPL code copied | independent Python implementation; Axelsson and Arbor book cited | met |
| Dashboard green | `python scripts/dashboard.py`; PR #72 head CI | met |

## 2. Workflow compliance

- Parent issue #70 was created before the branch and child issues.
- Child issues #71, #80, #82, and #87 map to P13.1-P13.4.
- Branch `feature/p13-als-ground` was created from `origin/main` at `2663b47`.
- Commits start with task IDs: `P13.1`, `P13.2`, `P13.3`, `P13.4`.
- `ROADMAP.md`, `CHANGE_LOG.md`, the note, and the docs were updated in the same commits.
- P13.2 and P13.3 merged `origin/main` twice as main advanced (P9 and P12/P9 changes).
- No tag, release, settings change, or FEMIC code change was made.

## 3. Gate evidence

`python scripts/dashboard.py` at `1bc56fb`: lint, format, types, tests, validator, and docs
all GREEN.

`python -m pytest -q` after the P10 merge: 327 passed, total coverage 87.89 percent.

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| PR #72 head run | `1bc56fb` plus the P10 merge | success | Green dashboard, Pre-commit parity, and Quality gates |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Initial facet-slope angle gate over-labelled low vegetation | First real-tile pass | Replaced with a point-to-triangle-vertex angle gate in P13.2 |
| P13.4 deferred FEMIC integration | One coastal tile, no exhaustive reference, near-ground noise remains | Recorded the reopening conditions in the report and roadmap |
| Main advanced during the phase | P9 and P12/P9 merged | Merged `origin/main`; resolved the changelog conflict; re-ran the dashboard |

## 6. Next phase

Recommended P14: **ground reference patch and second terrain validation**.

- Manually checked reference patch where class 1 and class 7 are resolved.
- A steep or interior forest LidarBC tile.
- Re-run class-2 recall, class-7 false-ground, HAG, and low-point policy metrics.
- Reopen the FEMIC decision only if those pass.

Alternative if the lab prioritizes product work over validation: P14 CHM/ITD
post-processing (buffer flags, small-tree flags, over-segmentation merging).

Do not start FEMIC integration from this phase.

## 7. Decision

- [x] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
