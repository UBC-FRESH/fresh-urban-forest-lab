# P45 citywide canopy-change sensitivity

Status: sensitivity analysis complete; close-out pending.

## Purpose

Test whether the P43 citywide 2 m net-canopy result is robust to the estimated vertical
offset and to the rejected 5 m scale choice.

This is a sensitivity envelope, not a measured vertical error or field validation.

## Offset sensitivity

Offsets applied to the 2018 canopy height:

| Offset | Earlier canopy | Later canopy | Net | Gain | Loss | Stable height |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| −1.0 m | 3,288 ha | 3,189 ha | **−99 ha** | 10.1% | 13.1% | +0.51 m |
| −0.5 m | 3,113 ha | 3,189 ha | **+76 ha** | 13.7% | 11.2% | +0.99 m |
| 0.0 m | 2,965 ha | 3,189 ha | **+223 ha** | 17.7% | 10.1% | +1.48 m |
| +0.5 m | 2,831 ha | 3,189 ha | **+358 ha** | 22.0% | 9.4% | +1.96 m |
| +1.0 m | 2,701 ha | 3,189 ha | **+488 ha** | 26.8% | 8.7% | +2.45 m |

The net sign is **not stable** across the ±1 m range. The defensible claim is therefore:

> The LiDAR surfaces show substantial canopy turnover, but the citywide net direction is
> not resolved by this screening method.

Do not claim a net gain or net loss from P43 without external vertical control.

## Scale comparison

| Product | Earlier canopy | Later canopy | Net | Valid overlap |
| --- | ---: | ---: | ---: | ---: |
| Released 2 m | 2,965 ha | 3,189 ha | +223 ha | 83.5 km² |
| Rejected 5 m | 4,346 ha | 3,189 ha | −1,156 ha | 83.5 km² |

The 5 m maximum aggregation inflated 2018 edge canopy and produced a spurious 28.8%
loss. It remains rejected.

## Implication for P44

The P44 `protect / investigate loss` cells are based on the P43 change screen. They are
useful as locations to investigate, but they are not proof of loss. The action layer
inherits the same vertical-offset and scale limits.

## Products

- `data/processed/vancouver_2022/change_sensitivity.json` (ignored)
- Source: P43 2 m and 5 m change grids under `/srv/shared-data`

## Limits

- Offset range is ±1.0 m, not a surveyed per-tile error.
- Classification, co-registration, and scale effects are not captured.
- No tree survival, species, ownership, causal, or field-validation claim.

## P50 vertical-control update

P50 measured a near-zero ground-control offset: **+0.008 m** (bootstrap +0.004 to +0.011)
for 2018 ground minus the 2022 DEM. That does not support the assumed +1.0 m offset. The
correction to the P43 earlier surface is **+0.992 m** (range +0.989 to +0.996), and the
corrected 2 m screen is about **−95 ha** (range −97 to −94 ha). This is a sampled control
result, not a citywide probability sample or final net-loss claim.

The ±1.0 m envelope above remains useful as a sensitivity range, but it is no longer the
best available estimate of the vertical offset. See `notes/reports/p50-vertical-control.md`.
