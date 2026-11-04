# P18 close-out: CHM/ITD post-processing exports and smoke test

Phase: P18 CHM/ITD post-processing exports and smoke test
Parent issue: #116
Pull request: the P18 PR, `feature/p18-itd-exports` into `main`
Evidence head: the P18.1 commit
Report commit: the commit that adds this report
Date: 2026-11-04
Status: approved; merge and close-out in progress

## Recommendation

Approve these actions. The agent carries them out in this order and reads back each result.

1. Squash-merge the P18 pull request and delete `feature/p18-itd-exports`.
2. Close parent issue #116 and child issue #117 with a closeout comment that cites the merge
   commit.
3. Recommend P19: a visual audit of the merge reduction on the demo, with before/after maps
   and a decision on whether the default merge thresholds are too aggressive.

Settings changes: none.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Opt-in CLI post-processing | `detect-trees --postprocess` | met |
| Kept-crown GeoJSON | `--out` | met |
| Sidecar summary | `<out>.summary.json` or `--summary` | met |
| Default command unchanged | early-return path; existing test | met |
| Demo smoke counts | 859 detected, 701 kept, 57 groups | met with limit |
| Stress buffer path | 50 m buffer flags 5 | met |
| CLI test | `test_detect_trees_postprocess_writes_summary` | met |
| Dashboard green | `python scripts/dashboard.py`; PR CI | met |

## 2. Workflow compliance

- Parent issue #116 was created before the branch and child issue.
- Child issue #117 is P18.1.
- Branch `feature/p18-itd-exports` was created from `origin/main` at `a5f12b2`.
- The commit starts with `P18.1`.
- `ROADMAP.md`, `CHANGE_LOG.md`, the report, and docs were updated.
- No tag, release, settings change, or default detector change was made.

## 3. Gate evidence

`python scripts/dashboard.py`: lint, format, types, tests, validator, and docs all GREEN.

`python -m pytest -q`: 347 passed, total coverage 87.79 percent.

## 4. CI evidence

The P18 pull request runs the Green dashboard, Pre-commit parity, and Quality gates. The
merge commit is recorded on the parent issue after the merge.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| 10 m buffer flags nothing on the demo | The demo is large and interior | Ran a 50 m stress configuration and recorded 5 flags |
| Small-tree flag not exercised | The detector minimum height is above the flag threshold | Recorded as a limit; a lower-height run is possible later |
| Merge reduces 859 to 701 | The CHM heuristic merges 158 source crowns | Flagged for visual audit before operational use |

## 6. Next phase

Recommended P19: visual audit of the merge reduction.

- Render before/after crown maps for the demo.
- Review the 57 merge groups for false merges.
- Decide whether `merge_max_area_ratio=0.6` and `merge_max_height_delta_m=2.0` are too
  aggressive.
- Keep the default detector unchanged.

Alternative: expose the summary in the dataset report/API or run the ground adapter on a
second tile.

## 7. Decision

- [x] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
