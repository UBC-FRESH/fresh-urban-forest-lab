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
  - protect / investigate loss: **546**
  - monitor: **101**
  - expand canopy: **77**
  - plant + cool: **50**
  - structural shade / retain: **23**

The protect-loss branch is now populated by the citywide observed-loss cells. The action
rule is unchanged and remains a relative screen.

## Correction

A first refresh declared only 39 protect-loss cells because it did not use the canonical
P43 citywide cells. The corrected build uses
`data/processed/change_vancouver_2018_2022_citywide/canopy_change.json`; the action counts
above supersede that first run.

## Limits

- P43 change is a 2 m thresholded LiDAR comparison with a recorded point stride and
  acquisition/classification/vertical/co-registration differences; it is not tree
  survival, growth, species change, ownership, or causal attribution.
- The action rule is a deterministic relative screen, not a planting plan, cost, utility,
  access, ownership, or field-validated recommendation.
- No causal claim.
