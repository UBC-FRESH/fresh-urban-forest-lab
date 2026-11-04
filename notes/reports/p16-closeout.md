# P16 close-out: optional FEMIC ground-adapter implementation

Phase: P16 Optional FEMIC ground-adapter implementation
Parent issue: #103
Pull request: the P16 PR, `feature/p16-ground-adapter` into `main`
Evidence head: the P16.1 commit
Report commit: the commit that adds this report
Date: 2026-11-04
Status: approved; merge and close-out in progress

## Recommendation

Approve these actions. The agent carries them out in this order and reads back each result.

1. Squash-merge the P16 pull request and delete `feature/p16-ground-adapter`.
2. Close parent issue #103 and child issue #104 with a closeout comment that cites the merge
   commit.
3. Launch P17: CHM/ITD post-processing (buffer flags, small-tree flags, over-segmentation
   merging).

Settings changes: none.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Sidecar writer | `write_ground_bundle`; `ground.laz`, `manifest.json`, `qa.json` | met |
| Extra dimensions | `is_ground`, `hag`, `is_low`, `ref_class` | met |
| Versioned manifest and QA | `femic.ground-bundle.v1`, `femic.ground-qa.v1` | met |
| Hashes and provenance | input/output/QA hashes, parameter hash, method block | met |
| Warnings | missing CRS, missing vertical datum, weak class-2 support, TIN/SOR warnings | met |
| CLI | `ground-adapter`, opt-in, not in default paths | met |
| Contract tests | synthetic LAZ, failure modes, CLI | met |
| Real-tile smoke | Golden-area tile, 113,775 points, 5.8 s | met with local-only limit |
| Dashboard green | `python scripts/dashboard.py`; PR CI | met |

## 2. Workflow compliance

- Parent issue #103 was created before the branch and child issue.
- Child issue #104 is P16.1.
- Branch `feature/p16-ground-adapter` was created from `origin/main` at `01c43e5`.
- The commit starts with `P16.1`.
- `ROADMAP.md`, `CHANGE_LOG.md`, the report, API docs, and public docs were updated.
- No tag, release, settings change, or FEMIC code change was made.

## 3. Gate evidence

`python scripts/dashboard.py`: lint, format, types, tests, validator, and docs all GREEN.

`python -m pytest -q`: 337 passed, total coverage 87.68 percent.

## 4. CI evidence

The P16 pull request runs the Green dashboard, Pre-commit parity, and Quality gates. The
merge commit is recorded on the parent issue after the merge.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Real-tile smoke is local, not CI | The test needs a large LAZ and network-free CI | Recorded the command and result in the P16 report |
| Low-point count is high on the steep tile | Many points sit within 0.15 m of the predicted surface | Documented that the flag is downstream, not a ground label |

## 6. Next phase

P17: CHM/ITD post-processing.

- buffer flags for edge crowns;
- small-tree/understory flags;
- over-segmentation merging for CHM-based crowns;
- tests and docs.

This is a product-value step and does not change the ground lane.

## 7. Decision

- [x] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
