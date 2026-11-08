# P44 citywide canopy-action refresh

Parent issue: #216
Branch: `feature/p44-citywide-action`
Status: planned

## Goal

Refresh the P42 action screen with the P43 citywide change product so observed gain/loss
is available for all 797 action cells, not only the 18 downtown pilot cells.

The action logic is unchanged: it remains a deterministic screening rule, not a planting
plan, cost model, utility check, ownership claim, or causal forecast.

## Inputs

- P38 shade/equity cells
- P39 gap/opportunity cells
- P40 heat-equity cells
- P43 citywide canopy-change cells (2 m source grid)

## Acceptance

- 797 action cells are rebuilt with P43 change.
- `change_observed` is true for all cells with P43 coverage.
- The `protect / investigate loss` branch is populated by observed loss cells.
- Action counts and loss-cell locations are reported.
- API/UI remain compatible; no new endpoint or layer is required.
- Dashboard and browser smoke pass.
