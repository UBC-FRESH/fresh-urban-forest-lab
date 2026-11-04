# P15 close-out: manual ground reference and optional FEMIC adapter design

Phase: P15 Manual ground reference and optional FEMIC adapter design
Parent issue: #95
Pull request: the P15 PR, `feature/p15-ground-adapter` into `main`
Evidence head: the P15.3 commit
Report commit: the commit that adds this report
Date: 2026-11-04
Status: approved; merge and close-out in progress

## Recommendation

Approve these actions. The agent carries them out in this order and reads back each result.

1. Squash-merge the P15 pull request and delete `feature/p15-ground-adapter`.
2. Close parent issue #95 and child issues #96, #97, and #98 with a closeout comment that
   cites the merge commit.
3. Do not start a new implementation phase automatically. Recommend P16: optional FEMIC
   adapter implementation with contract tests, or CHM/ITD post-processing.

Settings changes: none.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Manually checked 20 m reference patch | Golden-area patch, 6,393 points, side/top view | met with limit |
| Patch metrics | recall 0.9507; high-confidence false-ground 3.14%; HAG p99 0.0434 m | met |
| Optional FEMIC adapter design | `notes/design/femic-ground-adapter.md`; ADR 0007 | met |
| No default product change | sidecar contract; no FEMIC import; classifier opt-in | met |
| Dashboard green | `python scripts/dashboard.py`; PR CI | met |

## 2. Workflow compliance

- Parent issue #95 was created before the branch and child issues.
- Child issues #96, #97, and #98 map to P15.1-P15.3.
- Branch `feature/p15-ground-adapter` was created from `origin/main` at `9444b11`.
- Commits start with task IDs: `P15.1`, `P15.2`, `P15.3`.
- `ROADMAP.md`, `CHANGE_LOG.md`, the notes, and the docs were updated.
- No tag, release, settings change, or FEMIC code change was made.

## 3. Gate evidence

`python scripts/dashboard.py`: lint, format, types, tests, validator, and docs all GREEN.

`python -m pytest -q`: 331 passed, total coverage 87.66 percent.

## 4. CI evidence

The P15 pull request runs the Green dashboard, Pre-commit parity, and Quality gates. The
merge commit is recorded on the parent issue after the merge.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Manual check is visual, not point-by-point | Point labels are not available in the source product | Recorded exactly what the side view confirms and what it does not |
| Adapter is designed but not implemented | P15 scope is design and reference work | Recorded P16 as the implementation candidate |

## 6. Next phase

Recommended P16: **optional FEMIC adapter implementation with contract tests**.

- Implement the sidecar bundle writer against a tiny synthetic LAZ.
- Validate the manifest and QA schemas, hashes, extra dimensions, and failure modes.
- Keep the adapter optional and out of the default FEMIC path.
- Run a real-tile smoke test locally, not in CI.

Alternative: CHM/ITD post-processing (buffer flags, small-tree flags, over-segmentation
merging).

## 7. Decision

- [x] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
