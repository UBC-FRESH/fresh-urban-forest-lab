# P21 close-out: ground-adapter second-tile smoke test

Phase: P21 Ground-adapter second-tile smoke test
Parent issue: #126
Pull request: the P21 PR, `feature/p21-ground-smoke` into `main`
Evidence head: the P21.1 commit
Report commit: the commit that adds this report
Date: 2026-11-04
Status: approved; merge and close-out in progress

## Recommendation

Approve these actions. The agent carries them out in this order and reads back each result.

1. Squash-merge the P21 pull request and delete `feature/p21-ground-smoke`.
2. Close parent issue #126 and child issue #127 with a closeout comment that cites the merge
   commit.
3. Recommend P22: an optional FEMIC-side reader prototype for the ground bundle, or a manual
   point-label validation patch.

Settings changes: none.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Coastal bundle written | `runtime/p21/coastal_bundle` | met |
| Schema validation | `femic.ground-bundle.v1`, `femic.ground-qa.v1` | met |
| QA fields | counts, HAG, SOR, seeds, iterations, warnings | met |
| Golden comparison | P16 smoke values | met |
| No adapter defect | adapter code unchanged | met |
| Dashboard green | `python scripts/dashboard.py`; PR CI | met |

## 2. Workflow compliance

- Parent issue #126 was created before the branch and child issue.
- Child issue #127 is P21.1.
- Branch `feature/p21-ground-smoke` was created from `main` at `f0502f4`.
- The commit starts with `P21.1`.
- `ROADMAP.md`, `CHANGE_LOG.md`, the report, and docs were updated.
- No tag, release, settings change, or adapter code change was made.

## 3. Gate evidence

`python scripts/dashboard.py`: lint, format, types, tests, validator, and docs all GREEN.

`python -m pytest -q`: 353 passed, total coverage 87.82 percent.

## 4. CI evidence

The P21 pull request runs the Green dashboard, Pre-commit parity, and Quality gates. The
merge commit is recorded on the parent issue after the merge.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Real-tile smoke is local, not CI | The test needs a large LAZ and network-free CI | Recorded the exact tile, counts, and runtime |
| Low-point fraction differs sharply | Coastal and Golden point distributions differ | Recorded as data, not a defect |

## 6. Next phase

Recommended P22: optional FEMIC-side reader prototype.

- Read `ground.laz`, `manifest.json`, and `qa.json`.
- Validate hashes and schema versions.
- Expose a small read-only adapter, not a default product.
- Keep the bundle and reader optional.

Alternative: a manual point-label validation patch for the ground and crown lanes.

## 7. Decision

- [x] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
