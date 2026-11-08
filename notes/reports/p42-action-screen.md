# P42 integrated canopy-action screening

Status: screening product built; close-out pending.

## What it does

Joins P38 shade/equity, P39 gaps, P40 heat equity, and P41 observed change by global
400 m cell id and assigns one deterministic action label.

| Condition | Action |
| --- | --- |
| P41 change is loss | protect / investigate loss |
| high heat + high gap | plant + cool |
| high heat + low gap | structural shade / retain |
| low heat + high gap | expand canopy |
| low heat + low gap | monitor |

`high heat` means P40 tier `high` or the P40 index is at/above the city median.
`high gap` means P39 tier `high` or gap area is at/above the city median.
These are relative screening rules, not thresholds from a field study.

## Vancouver result

- 797 cells joined from P38/P39/P40.
- Change observed in 18 cells (P41 downtown pilot only).
- Action counts:
  - plant + cool: **270**
  - monitor: **253**
  - expand canopy: **145**
  - structural shade / retain: **129**
  - protect / investigate loss: **0** (the pilot change cells are net gain)

The absence of `protect_loss` is a real consequence of the pilot data, not a
missing branch. The branch is implemented and unit-tested.

## Products

Under `data/processed/vancouver_2022/`:

- `canopy_action.json`
- `canopy_action.geojson`
- `canopy_action.png`
- `canopy_action_meta.json`

API: `/api/canopy-action` and `/api/canopy-action.geojson`. Map: **canopy action**
toggle and sidebar summary.

## Limits

- **Not a planting plan.** Cost, utilities, ownership, access, soil, irrigation,
  maintenance, and field validation are not modelled.
- **Relative rules.** Median/tier thresholds are city-relative and have not been
  calibrated to outcomes.
- **Change coverage is partial.** Only the 2 km² downtown P41 pilot is observed; all
  other cells are explicitly `not observed`.
- **No causal claim.** A cell labelled plant/cool is not proof that planting there
  will produce a measured temperature reduction.
- **No ownership claim.**
