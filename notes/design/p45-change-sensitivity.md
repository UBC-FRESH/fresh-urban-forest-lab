# P45 citywide canopy-change sensitivity and validation

Parent issue: #224
Branch: `feature/p45-change-sensitivity`
Status: planned

## Goal

Quantify how the P43 citywide 2 m change screen responds to the estimated +1.0 m vertical
offset and to the rejected 5 m scale choice, then state a defensible claim range.

The phase does not validate tree survival, species change, ownership, or causation.

## Method

- Load the P43 2 m `change_grid.npz`.
- Apply offsets of −1.0, −0.5, 0.0, +0.5, and +1.0 m to the 2018 canopy height.
- Recompute 2 m canopy change: earlier/later canopy, gain, loss, stable, net, and stable
  height change.
- Compare the released 2 m result with the rejected 5 m maximum-aggregation result.
- Record the range and a claim rule: if the net sign changes within the offset range, do
  not claim a direction; report the range.

## Acceptance

- Sensitivity JSON and method note are written.
- The 2 m and 5 m results are compared explicitly.
- The note states the offset range, net range, and sign stability.
- No change to the released P43 product without review.
- Dashboard green.
