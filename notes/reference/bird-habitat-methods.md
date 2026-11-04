# Bird habitat and demography: data, guilds, and evidence tiers

Status: P10.1 method note, 2026-11-04.

## Data position

No local bird survey or mark-recapture dataset is bundled with this repository. The P10
layer is therefore a **prior-driven screening model** built on:

- LiDAR/tree structural metrics;
- published habitat-structure associations;
- literature/expert survival and fecundity priors;
- optional user-supplied point-count or eBird-export CSV files.

It is not a local density estimate or a population forecast.

## Three different quantities

- **Relative abundance index**: a unitless screening score from habitat suitability and a
  guild coefficient. It is not birds per hectare.
- **Density**: birds per unit area, requiring distance sampling, territory mapping, or a
  calibrated model. Not provided.
- **Survival / lambda**: demographic rates and population growth. The built-in projection
  uses literature priors and a two-stage matrix. It is not a site-specific survival
  estimate without mark-recapture, nest, or resighting data.

## Guilds

The model uses five transparent guilds:

| Guild | Structural emphasis | Base abundance prior |
| --- | --- | --- |
| Canopy insectivores | canopy height, foliage diversity, layering | 12 |
| Cavity nesters | mature trees, native share, layering | 5 |
| Ground foragers | open/gap habitat, native share | 9 |
| Migrants | canopy structure, native share | 7 |
| Urban adapters | open/gap habitat | 20 |

The coefficients are priors. They are not fitted to Vancouver bird counts.

## Structural metrics

- live-tree count;
- native share;
- mean and p95 height;
- raster canopy cover and gap fraction;
- vertical complexity (standard deviation of heights / mean height);
- foliage-height diversity (Shannon diversity of crown volume across 0–2, 2–5, 5–10, 10–15,
  15–20, and 20+ m bands);
- layering count (bands with at least five percent of crown volume);
- DBH size diversity;
- weighted composite habitat score.

## Demographic model

Two stages, juvenile and adult:

```text
J(t+1) = fecundity * A(t)
A(t+1) = juvenile_survival * J(t) + adult_survival * A(t)
```

The habitat score modifies fecundity and survival. Lambda is the dominant eigenvalue of the
matrix. The output reports low/base/high prior lambda and numerical sensitivity.

## Optional observations

A CSV can be supplied later with columns:

```text
species,lon,lat,count,guild
```

The loader validates numeric fields. A future P10.3 calibration can use holdout
observations to fit guild coefficients, but only with a documented eBird/local-survey
licence and sampling design.

## What would change the conclusion

- local point counts with distance sampling;
- repeated surveys to estimate detection probability;
- mark-recapture or resighting for survival;
- nest monitoring for fecundity;
- species-level habitat thresholds;
- an expert review of guild assignments.

## Evidence labels

- `prior`: guild coefficients, suitability curves, survival/fecundity.
- `scenario`: a scenario projection.
- `calibrated`: only after local fitting.
- `measured`: only after field observation.

## Privacy and data terms

eBird data access requires acceptance of its terms. Local survey data may have location
sensitivity. Do not publish precise nest or sensitive-species locations without permission.
