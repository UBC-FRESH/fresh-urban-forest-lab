# P51 corrected P43 product

Status: corrected product built; P51.3 downstream refresh pending.

## Input

- Source P43 product:
  `change_vancouver_2018_2022_citywide_2m/`
- P51 control estimate:
  `vertical_control_sample34.json`
- P43 assumed vertical offset: **+1.0 m**
- Measured 2018-ground minus 2022-DEM offset: **+0.015 m**
- Correction to the earlier surface: **+0.985 m**
  (bootstrap **+0.984 to +0.987 m**)

## Output

Versioned product:

`data/processed/change_vancouver_2018_2022_citywide_2m_control/`

The original P43 product is unchanged. The corrected product includes `change.json`,
`change.png`, `change_grid.npz`, and `control_metadata.json`.

## Metrics

| Metric | Corrected 2 m product |
| --- | ---: |
| Earlier canopy | 3,281.15 ha |
| Later canopy | 3,188.65 ha |
| Gain | 334.43 ha |
| Loss | 426.94 ha |
| Stable canopy | 2,854.21 ha |
| Net | **−92.50 ha** |
| Mean height change on stable canopy | **+0.523 m** |

Compare with the original P43 2 m result: **+223 ha** net, +1.475 m stable height.

## Caveats

- The correction is a constant offset from a 34-tile spatial sample, not a citywide
  probability sample.
- One western control tile is a −0.43 m outlier; 30/31 tiles are within ±0.15 m.
- No class-6 roof control was available.
- Classification, co-registration, scale, edge, and acquisition-season effects remain.
- This is a corrected **screen**, not a final citywide net-loss claim.
- Downstream corrected P44/P46 data and the P38 rebuild are documented in
`notes/reports/p51-downstream-refresh.md`; public API/UI remains on the original products.
