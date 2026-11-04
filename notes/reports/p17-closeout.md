# P17 close-out: CHM/ITD post-processing

Phase: P17 CHM/ITD post-processing
Parent issue: #113
Pull request: the P17 PR, `feature/p17-itd-postprocess` into `main`
Evidence head: the P17.1 commit
Report commit: the commit that adds this report
Date: 2026-11-04
Status: approved; merge and close-out in progress

## Recommendation

Approve these actions. The agent carries them out in this order and reads back each result.

1. Squash-merge the P17 pull request and delete `feature/p17-itd-postprocess`.
2. Close parent issue #113 and child issue #114 with a closeout comment that cites the merge
   commit.
3. Recommend P18: a real-dataset smoke test of the post-processing on the UBC 2021 crown
   product, or a small UI/exports integration.

Settings changes: none.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Edge buffer flags | `postprocess_trees`; tests | met |
| Small-tree flags | strict height threshold; tests | met |
| Conservative merge | source-ID groups; tests | met |
| `kept()` filtering | excludes both flag sets; test | met |
| JSON summary | `to_dict`; test | met |
| Default detection unchanged | no change to `detect_trees` | met |
| Dashboard green | `python scripts/dashboard.py`; PR CI | met |

## 2. Workflow compliance

- Parent issue #113 was created before the branch and child issue.
- Child issue #114 is P17.1.
- Branch `feature/p17-itd-postprocess` was created from `origin/main` at `71f94d4`.
- The commit starts with `P17.1`.
- `ROADMAP.md`, `CHANGE_LOG.md`, API docs, and public docs were updated.
- No tag, release, settings change, or default detection change was made.

## 3. Gate evidence

`python scripts/dashboard.py`: lint, format, types, tests, validator, and docs all GREEN.

`python -m pytest -q`: 346 passed, total coverage 87.76 percent.

## 4. CI evidence

The P17 pull request runs the Green dashboard, Pre-commit parity, and Quality gates. The
merge commit is recorded on the parent issue after the merge.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Merge rule is a CHM heuristic, not a point-cloud resolver | P17 scope is post-processing of CHM crowns | Recorded the narrow rule and its limits in the module docstring and docs |
| No real-dataset smoke test in this phase | The synthetic tests cover the contract | Recommended P18 for a real crown-product smoke test |

## 6. Next phase

Recommended P18: real-dataset smoke test and exports integration.

- Run `detect_trees` + `postprocess_trees` on the UBC 2021 CHM and the demo dataset.
- Report kept/flagged/merged counts and the effect on cover/crown metrics.
- Add the summary to the dataset report or CLI output if it is useful.
- Keep the default detector unchanged.

## 7. Decision

- [x] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
