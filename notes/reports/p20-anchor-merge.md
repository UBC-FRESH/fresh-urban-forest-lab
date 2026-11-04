# P20 non-transitive anchor merge and manual audit patch

Date: 2026-11-04
Phase: P20
Parent issue: #122
Task: #123
Status: anchor merge implemented; synthetic audit patch passes; demo result unchanged

## Anchor rule

The merge now uses a non-transitive anchor pass:

1. Sort crowns by area, height, and ID.
2. The largest unassigned crown becomes an anchor.
3. It may absorb much smaller, height-similar crowns whose centres fall inside its
   equivalent radius.
4. An absorbed crown cannot become an anchor.
5. Group-size and group-extent caps still apply.

This removes the union-find chain by construction, not only by a group cap.

## Synthetic manual audit patch

The test patch has known labels:

| Pair | Expected | Result |
| --- | --- | --- |
| `true-left` + `true-right` (split crown) | merge | merged |
| `distinct-left` + `distinct-right` (similar area) | keep separate | kept |
| `far` | keep | kept |

Additional tests cover:

- an absorbed crown cannot anchor another crown;
- one anchor can absorb multiple small crowns within the caps;
- group-extent and group-member guards still apply.

## Demo comparison

`data/demo/ubc_core`, `min-height=3`, buffer 10, small threshold 2:

| Rule | Detected | Groups | Source crowns merged | Kept | Largest group |
| --- | ---: | ---: | ---: | ---: | --- |
| P19 guarded union-find | 859 | 3 | 6 | 856 | 2 crowns, 0 m |
| P20 anchor | 859 | 3 | 6 | 856 | 2 crowns, 0 m |

The anchor rule gives the same demo result. The old 57 groups were transitive chain
artifacts, not local split crowns. The three remaining groups are duplicate/near-duplicate
maxima at the same XY location.

## Interpretation

- The anchor rule is structurally safer than union-find.
- It does not recover more local merges on this demo; the demo does not contain obvious
  local split crowns beyond the three duplicates.
- The synthetic audit patch shows the rule can merge a known split crown without merging
  similar distinct crowns.
- The under-merging concern is now a data question, not a chain-collapse bug. A real manual
  crown patch is still needed.

## Limits

- One demo dataset and one synthetic audit patch.
- No orthophoto or field crown labels.
- The anchor rule is still a CHM heuristic.
- The default detector is unchanged.
