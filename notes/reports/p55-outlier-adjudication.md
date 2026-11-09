# P55 vertical-control outlier adjudication

Status: complete; constant correction retained. PR review pending.

## Outliers

The four western tiles excluded from the P53 stability gate have broad class-2 ground
distributions, not a single isolated spike:

| Tile | Count | Median | P10 | P90 | Within 0.15 m of median |
| --- | ---: | ---: | ---: | ---: | ---: |
| `4830E_54530N` | 1,147 | −0.478 m | −1.226 m | −0.092 m | 36.3% |
| `4840E_54520N` | 2,290 | −0.233 m | −0.550 m | −0.044 m | 63.4% |
| `4840E_54530N` | 6,985 | −0.430 m | −1.239 m | +0.179 m | 17.2% |
| `4840E_54540N` | 168 | −0.305 m | −0.956 m | +0.015 m | 25.6% |

Adjacent eastern/inlier tiles are near zero, for example:

- `4850E_54520N`: −0.079 m
- `4850E_54530N`: +0.008 m
- `4850E_54540N`: +0.027 m
- `4860E_54530N`: +0.015 m
- `4840E_54560N`: +0.012 m

The outlier signal is localized to the western edge and is broad within each tile. It looks
more like a local ground/classification/terrain effect than a clean constant vertical bias.

## Stable-surface check

- 2018 class-6 building roofs are absent from the sampled LAS classes.
- No independent roof/road/ICESat-2/GEDI control was available for this adjudication.
- The class-2 ground proxy is the only stable-surface control.

## Decision

Retain the full-sample constant offset **+0.011 m** and the P53 outlier caveat.

Do **not** introduce a four-tile local correction. The local medians are broad, one tile
has only 168 observations, and there is no independent surface to distinguish real ground
change from classification error. The four tiles remain in the control count; they are
excluded only from the stability gate.

No corrected product is rebuilt or relabeled. P53/P54 corrected products remain the
full-control version already published, with the western outlier caveat.

## Release wording

- Corrected P43: full-control screen, net **−94.3 ha**, **+0.519 m** stable height.
- Corrected action/turnover: full-control sidecars, selectable and default in the UI.
- Original P43 lineage remains selectable.
- Not a final citywide net-loss claim, field validation, survival, ownership, or planting
  plan.

## Verification

- The P53/P54 browser smoke and dashboard remain the release checks; no code or UI change
  was made in P55.
