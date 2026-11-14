# P60 independent control for western vertical-control tiles

Status: implementation complete; PR review pending.

## Question

Do ICESat-2 or GEDI provide enough independent ground/height control to decide whether the
four western P53 outliers require a local correction?

Target tiles:

| Tile | Class-2 median vs 2022 DEM |
| --- | ---: |
| `4830E_54530N` | −0.478 m |
| `4840E_54520N` | −0.233 m |
| `4840E_54530N` | −0.430 m |
| `4840E_54540N` | −0.305 m |

Adjacent inlier medians are near zero, for example `4850E_54530N` at +0.008 m.

## Data searched

- **ICESat-2 ATL08 v007** through OpenAltimetry: 55 date-track queries, 1,345 returned
  points in the 5 × 5 km search box. DOI: `10.5067/ATLAS/ATL08.007`.
- **ICESat-2 ATL03** through OpenAltimetry: high-confidence photons only, 19 date-track
  queries, 821 photons inside the four target tiles.
- **GEDI02_A v003** through Harmony: 100 input granules, 62 spatially and variable
  subset files. DOI: `10.5067/GEDI/GEDI02_A.003`.
- NASA Earthdata Login was used for access. These are public NASA products; raw and subset
  granules are not tracked in the repository.
- No independent geodetic benchmark or stable roof/road control was used.

## Coverage

| Target tile | ATL08 points | ATL03 high-confidence photons | GEDI screened points |
| --- | ---: | ---: | ---: |
| `4830E_54530N` | 0 | 0 | 0 |
| `4840E_54520N` | 0 | 0 | 0 |
| `4840E_54530N` | 1 | 665 | 9 |
| `4840E_54540N` | 1 | 156 | 4 |

The GEDI screen required `surface_flag == 1`, `degrade_flag == 0`, sensitivity 0.5–1.0,
plausible elevation and canopy height, and a gross vertical window against the 2022 DEM.
One `4840E_54520N` candidate was rejected by the vertical window.

The independent points do not cover `4830E_54530N` or `4840E_54520N`. ATL03 high-confidence
photons are not a ground-classified control and were not used as one.

## Relative check

For the two target tiles with usable GEDI samples, median GEDI lowest-mode elevation minus
the 2022 DEM was:

| Tile | n | GEDI − 2022 DEM |
| --- | ---: | ---: |
| `4840E_54530N` | 9 | −20.45 m |
| `4840E_54540N` | 4 | −19.13 m |

The three inlier tiles with GEDI samples were −18.84 m, −18.77 m, and −18.83 m. After
centering on the inlier median, the target residuals are about **−1.6 m** and **−0.3 m**.
The sample is too sparse, and the two architectures are not independent of canopy/terrain
conditions, to turn this into a local correction.

## Vertical datum

GEDI and ATL08 heights are referenced to the WGS84 ellipsoid. No geoid conversion to
CGVD28GVRD was applied, so the absolute comparison to the 2018/2022 orthometric surfaces is
not resolved. The numbers above are relative, tile-centered checks only.

## Decision

**Inconclusive; retain the full-sample constant correction of +0.011 m and the western
outlier caveat.**

- No local four-tile correction is supported.
- No corrected product is rebuilt or relabeled.
- `4830E_54530N` remains untested by an independent surface.
- The four tiles remain in the control count and are excluded only from the stability gate.
- This is not field validation, a survey-grade accuracy assessment, or a citywide net-loss
  claim.

## Follow-up options

1. Obtain a documented geoid model and reprocess GEDI/ATL08 to CGVD28GVRD.
2. Add more independent tracks or stable roof/road control, especially for
   `4830E_54530N`.
3. Leave the constant correction and caveat in place.

## Verification

- External coverage and screening counts: `notes/reports/p60-external-sample.json`.
- Dashboard run required before merge.
- No product or UI behavior changed.
