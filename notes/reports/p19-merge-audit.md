# P19 merge-reduction audit

Date: 2026-11-04
Phase: P19
Parent issue: #119
Task: #120
Status: audit complete; guard added; default merge now conservative

## Old merge behaviour

P17/P18 merged 859 detected crowns into 701 on `data/demo/ubc_core`:

- 57 merge groups;
- 215 source crowns;
- one group with **67 members**;
- 14 groups of 3, 4 groups of 4, and one group each of 5, 6, and 9 members.

The largest group spanned **4,647 m x 4,332 m**, effectively the whole demo. The next largest
spanned 533 m x 380 m, and the third spanned 419 m x 380 m. This is transitive chain collapse,
not over-segmentation repair.

A visual audit map was rendered at `runtime/p19/merge_audit.png` (not tracked). The old
67-member group (red) is scattered across the entire campus; the guarded groups (blue x) are
local.

## Cause

The pairwise rule was correct for a single pair, but union-find made it transitive. A chain
of locally plausible pairs could connect crowns kilometres apart. The old rule had no group
size or spatial extent cap.

## Guard

Added two parameters:

- `merge_max_group_members` (default 4);
- `merge_max_group_extent_m` (default 30 m, XY bounding-box diagonal).

A union is rejected when the combined group would exceed either cap. The CLI now exposes:

- `--merge-max-area-ratio`
- `--merge-max-height-delta`
- `--merge-max-group-members`
- `--merge-max-group-extent`

## New demo result

| Metric | Old | Guarded |
| --- | ---: | ---: |
| Detected crowns | 859 | 859 |
| Merge groups | 57 | 3 |
| Source crowns merged | 215 | 6 |
| Kept crowns | 701 | 856 |
| Largest group | 67 members, 4.6 km extent | 2 members, 0 m extent |

The three guarded groups are duplicate/near-duplicate maxima at the same XY location. The
guarded merge is highly conservative: it avoids the false chain collapse, but it may leave
real over-segmentation unrepaired. That is the safer default.

## Decision

- Keep the group-size and group-extent guards.
- Do not change the area-ratio or height-delta defaults in this phase.
- Treat the guarded merge as a safety filter, not a full instance-segmentation solver.
- A future phase can add a non-transitive or spatially constrained match if real
  over-segmentation needs repair.

## Limits

- One demo dataset and a visual audit, not a field or manual crown label.
- The guarded merge only found 3 local groups; under-merging is likely.
- The old chain-collapse evidence is strong; the new threshold values are conservative
  defaults, not calibrated optima.
- The default detector is unchanged.
