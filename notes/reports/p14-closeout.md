# P14 close-out: ground reference and second terrain validation

Phase: P14 Ground reference and second terrain validation
Parent issue: #89
Pull request: the P14 PR, `feature/p14-ground-reference` into `main`
Evidence head: the P14.3 commit
Report commit: the commit that adds this report
Date: 2026-11-04
Status: approved; merge and close-out in progress

## Recommendation

Approve these actions. The agent carries them out in this order and reads back each result.

1. Squash-merge the P14 pull request and delete `feature/p14-ground-reference`.
2. Close parent issue #89 and child issues #90, #91, and #92 with a closeout comment that
   cites the merge commit.
3. Do not start a new implementation phase automatically. Recommend P15: a manually
   labelled reference patch and an optional FEMIC adapter design.

Settings changes: none.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Reproducible reference construction | positive class 2; nearest class-2 surface; high-confidence negative HAG > 2 m; ambiguous 0-2 m excluded | met |
| Steep interior tile validation | Golden-area 2021 tile, 113,775 points, about 62 m relief | met |
| Coastal comparison | 2025 P13.2 tile | met |
| Class-2 recall and false-ground rate | coastal 0.9999 / 3.35%; steep 0.9634 / 4.65% | met |
| FEMIC decision revisit | optional adapter prototype approved; default pipeline unchanged | met |
| Dashboard green | `python scripts/dashboard.py`; PR CI | met |

## 2. Workflow compliance

- Parent issue #89 was created before the branch and child issues.
- Child issues #90, #91, and #92 map to P14.1-P14.3.
- Branch `feature/p14-ground-reference` was created from `origin/main` at `c57bc96`.
- Commits start with task IDs: `P14.1`, `P14.2`, `P14.3`.
- `ROADMAP.md`, `CHANGE_LOG.md`, the note, and the docs were updated.
- No tag, release, settings change, or FEMIC code change was made.

## 3. Gate evidence

`python scripts/dashboard.py`: lint, format, types, tests, validator, and docs all GREEN.

`python -m pytest -q`: 331 passed, total coverage 87.66 percent.

## 4. CI evidence

The P14 pull request runs the Green dashboard, Pre-commit parity, and Quality gates. The
merge commit is recorded on the parent issue after the merge.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| P13.4 deferred FEMIC integration; P14.3 approves an optional prototype | The reference and steep-tile evidence reduced the uncertainty | Recorded the conditions: manual patch, versioned optional adapter, stable contract |
| Reference is not manually labelled | Point-level labels are not available in the source product | Used a reproducible class-2 surface and excluded the ambiguous 0-2 m band |

## 6. Next phase

Recommended P15: **manual reference patch and optional FEMIC adapter design**.

- Label or verify a small patch where class 1/7 are resolved.
- Design an optional, versioned FEMIC adapter without changing the default product path.
- Keep the classifier opt-in until the manual patch passes.

Alternative: CHM/ITD post-processing (buffer flags, small-tree flags, over-segmentation
merging).

## 7. Decision

- [x] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
