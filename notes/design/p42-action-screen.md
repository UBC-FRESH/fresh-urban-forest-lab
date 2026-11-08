# P42 integrated canopy-action screening

Parent issue: #202
Branch: `feature/p42-action-screen`
Status: planned

## Goal

Join P38 shade/equity, P39 canopy gaps, P40 heat equity, and P41 observed change into
one 400 m screening layer with a transparent action label.

This is a decision-support screen, not a planting plan, cost model, utility check,
ownership claim, or causal forecast.

## Inputs

- P38 `heat_priority.json`: shade deficit, social equity, shade class.
- P39 `planting_opportunity.json`: gap area, street-adjacent gap, opportunity tier.
- P40 `heat_equity.json`: mean LST, heat-equity tier, five-part index.
- P41 `canopy_change.json`: observed gain/loss/stable for the downtown pilot only.

## Action logic

- `high heat` = P40 tier `high` or index at/above the median.
- `high gap` = P39 tier `high` or gap area at/above the median.
- `loss observed` = P41 class `loss`.
- Otherwise:
  - high heat + high gap → **plant + cool**
  - high heat + low gap → **structural shade / retain**
  - low heat + high gap → **expand canopy**
  - low heat + low gap → **monitor**

Missing change is `not observed`; the cell is still classified from P38–P40.

## Deliverables

- 400 m action cells with all joined fields and missing-data flags.
- JSON, GeoJSON, PNG, metadata.
- API, map toggle, sidebar summary.
- Method note with limits.

## Acceptance

- Every P38/P39/P40 cell is represented.
- Action labels are deterministic and documented.
- Missing P41 change is explicit, not imputed.
- API/UI are optional when the product is absent.
- No ownership, cost, utility, causal, or field-validation claim.
- Dashboard green.
