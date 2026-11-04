# P19 close-out: merge-reduction audit and guard

Phase: P19 Merge-reduction audit and guard
Parent issue: #119
Pull request: the P19 PR, `feature/p19-merge-audit` into `main`
Evidence head: the P19.1 commit
Report commit: the commit that adds this report
Date: 2026-11-04
Status: approved; merge and close-out in progress

## Recommendation

Approve these actions. The agent carries them out in this order and reads back each result.

1. Squash-merge the P19 pull request and delete `feature/p19-merge-audit`.
2. Close parent issue #119 and child issue #120 with a closeout comment that cites the merge
   commit.
3. Recommend P20: a spatially constrained, non-transitive crown merge with a small manual
   audit patch. The current guard prevents false merges but under-merges real
   over-segmentation.

Settings changes: none.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Audit old merge groups | 57 groups, 215 crowns, largest 67 over 4.6 km | met |
| Visual audit map | `runtime/p19/merge_audit.png` | met |
| Chain-collapse diagnosis | group size/extent evidence | met |
| Guarded rule | 4-member and 30 m extent caps | met |
| Demo result | 3 local groups, 859 -> 856 | met |
| CLI tuning options | four merge options on `detect-trees` | met |
| Guard tests | extent, member, invalid values | met |
| Dashboard green | `python scripts/dashboard.py`; PR CI | met |

## 2. Workflow compliance

- Parent issue #119 was created before the branch and child issue.
- Child issue #120 is P19.1.
- Branch `feature/p19-merge-audit` was created from `main` at `fed6263`.
- The commit starts with `P19.1`.
- `ROADMAP.md`, `CHANGE_LOG.md`, the report, and docs were updated.
- No tag, release, settings change, or default detector change was made.

## 3. Gate evidence

`python scripts/dashboard.py`: lint, format, types, tests, validator, and docs all GREEN.

`python -m pytest -q`: 350 passed, total coverage 87.82 percent.

## 4. CI evidence

The P19 pull request runs the Green dashboard, Pre-commit parity, and Quality gates. The
merge commit is recorded on the parent issue after the merge.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Guarded merge is highly conservative | The old transitive chain collapse was severe | Kept the guard; flagged under-merging as the next problem |
| No field crown labels | P19 is an audit, not a field validation | Recommended a manual audit patch in P20 |

## 6. Next phase

Recommended P20: spatially constrained, non-transitive crown merge.

- Build a small manual audit patch with checked crown labels.
- Replace or supplement union-find with a spatially constrained match.
- Compare false-merge and missed-merge rates.
- Keep the default detector unchanged until the audit passes.

## 7. Decision

- [x] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
