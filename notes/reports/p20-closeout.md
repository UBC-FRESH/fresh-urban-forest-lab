# P20 close-out: non-transitive crown merge and manual audit patch

Phase: P20 Non-transitive crown merge and manual audit patch
Parent issue: #122
Pull request: the P20 PR, `feature/p20-anchor-merge` into `main`
Evidence head: the P20.1 commit
Report commit: the commit that adds this report
Date: 2026-11-04
Status: approved; merge and close-out in progress

## Recommendation

Approve these actions. The agent carries them out in this order and reads back each result.

1. Squash-merge the P20 pull request and delete `feature/p20-anchor-merge`.
2. Close parent issue #122 and child issue #123 with a closeout comment that cites the merge
   commit.
3. Recommend P21: a real manual crown audit on a small patch with orthophoto or field
   evidence, or a return to the ground-adapter second-tile smoke test.

Settings changes: none.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Non-transitive anchor rule | `_merge_groups` anchor pass | met |
| Absorbed crown cannot anchor | unit test | met |
| Anchor absorbs multiple crowns | unit test | met |
| Synthetic audit patch | split crown merges, distinct crowns stay separate | met |
| Group caps retained | member/extent guards; tests | met |
| Demo comparison | P19 and P20 both 3 groups, 856 kept | met |
| Dashboard green | `python scripts/dashboard.py`; PR CI | met |

## 2. Workflow compliance

- Parent issue #122 was created before the branch and child issue.
- Child issue #123 is P20.1.
- Branch `feature/p20-anchor-merge` was created from `main` at `3daf89b`.
- The commit starts with `P20.1`.
- `ROADMAP.md`, `CHANGE_LOG.md`, the report, and docs were updated.
- No tag, release, settings change, or default detector change was made.

## 3. Gate evidence

`python scripts/dashboard.py`: lint, format, types, tests, validator, and docs all GREEN.

`python -m pytest -q`: 353 passed, total coverage 87.82 percent.

## 4. CI evidence

The P20 pull request runs the Green dashboard, Pre-commit parity, and Quality gates. The
merge commit is recorded on the parent issue after the merge.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Anchor rule does not increase demo merges | The old extra groups were chain artifacts, not local split crowns | Recorded that the demo lacks obvious local split crowns |
| Synthetic patch, not field labels | P20 has no orthophoto/field labels | Recommended P21 real manual audit |

## 6. Next phase

Recommended P21: real manual crown audit.

- Select a small real patch with an orthophoto or field crown sketch.
- Label split and distinct crowns.
- Compare the anchor rule against the labels.
- Decide whether to tune the area/height thresholds or keep the safety filter.

Alternative: return to the ground-adapter second-tile smoke test.

## 7. Decision

- [x] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
