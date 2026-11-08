# P53 full-city vertical control and corrected publication

Status: full control complete; corrected products published as a selectable change layer.

## Full sample

- 181/181 indexed 2018 tiles present; 78.04 GB.
- All downloads verified against the indexed SHA-256.
- 149 tiles produced class-2 ground observations.
- 965,995 paired observations.
- Median 2018-ground minus 2022-DEM offset: **+0.011 m**.
- Bootstrap 95% interval: **+0.010 to +0.012 m**.
- MAD: **0.050 m**.
- Per-tile medians: **−0.478 to +0.071 m**.
- Four western tiles are outliers at the 0.20 m stability threshold:
  `4830E_54530N`, `4840E_54520N`, `4840E_54530N`, `4840E_54540N`.
- Excluding those four outliers, 145/145 stability tiles are within ±0.15 m of the
  sample median; easting trend **+0.013 m**, northing trend **−0.082 m**.
- Gate: **pass with documented outlier exclusion**. The outlier tiles are retained in the
  control count, not silently deleted.

## Corrected P43

Versioned product:

`data/processed/change_vancouver_2018_2022_citywide_2m_control_full/`

- P43 assumed +1.0 m; measured correction to the earlier surface: **+0.989 m**
  (interval +0.988 to +0.990).
- Earlier canopy: 3,282.94 ha
- Later canopy: 3,188.65 ha
- Gain: 333.67 ha
- Loss: 427.96 ha
- Stable: 2,854.98 ha
- Net: **−94.29 ha**
- Stable-height change: **+0.519 m**

Original P43 remains **+223 ha** / **+1.475 m** and is unchanged.

## Corrected P44/P46 sidecars

P38 was rebuilt from public 2021 Census Profile CSVs and DA geometry.

P44 action counts:

- plant + cool: **162**
- monitor: **195**
- expand canopy: **110**
- structural shade: **113**
- protect / investigate loss: **217**

P46 turnover:

- high-tier cells: **260**
- total turnover area: **135.65 ha**

## Publication

The corrected change product is published as a **selectable sidecar**:

- original: `change.json` → existing +223 ha layer
- corrected: `change_control.json` → full P53 ground-control layer

The Change tab lists both. The original remains the default. The corrected layer is labelled
“full P53 ground-control corrected”. P44/P46 corrected products remain versioned data
sidecars; they are not silently substituted into the public action/turnover API.

## Verification

- Change API lists both products.
- Browser smoke:
  - default original: +223 ha, +1.48 m
  - selected corrected: −94 ha, +0.52 m
  - no page errors.
- Dashboard green.

## Limits

- Four western outlier tiles are excluded only from the stability gate; they remain in the
  control estimate.
- No class-6 roof control; class-2 ground is a proxy, not survey control.
- Classification, co-registration, scale, edge, and acquisition-season effects remain.
- This is a corrected screen, not a final citywide net-loss claim or field validation.
