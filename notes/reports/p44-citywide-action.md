# P44 citywide canopy-action refresh

Status: refreshed product built; close-out pending.

## What changed

The P42 action screen used the P41 downtown change product, so only 18 of 797 cells had
observed change. P44 rebuilds the same action logic with the P43 citywide change.

No new action categories or endpoints were added. The same `canopy_action` product,
API, and map layer are refreshed.

## Result

- 797 action cells
- P43 change observed in **797 / 797** cells
- Action counts:
  - plant + cool: **265**
  - monitor: **233**
  - expand canopy: **133**
  - structural shade / retain: **127**
  - protect / investigate loss: **39**

P42 comparison:

| Action | P42 (downtown change) | P44 (citywide change) |
| --- | ---: | ---: |
| plant + cool | 270 | 265 |
| monitor | 253 | 233 |
| expand canopy | 145 | 133 |
| structural shade | 129 | 127 |
| protect loss | 0 | 39 |

The loss branch is now populated by observed loss cells. The largest single net-loss cell
is `r19c07` at about **−1.23 ha**, P38 class `2A`, low heat tier, high gap tier. This is a
screening label, not a causal attribution.

## Limits

- The action rule is unchanged and remains a relative screen.
- P43 change is a 2 m thresholded LiDAR comparison with a +1.0 m DEM offset and a
  scale-sensitive method; it is not tree survival or growth.
- No cost, utilities, ownership, access, soil, irrigation, maintenance, or field
  validation.
- No causal claim.
