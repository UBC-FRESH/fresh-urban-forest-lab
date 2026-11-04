# P10 close-out: bird habitat and demography

Date: 2026-11-04
Phase: P10
Parent issue: #43
Branch: `feature/p10-birds`
Implementation head: `10dac0d`
Status: ready for review

## Summary

P10 adds a 3D canopy habitat layer, guild-level relative abundance, and a prior-driven
two-stage demographic projection. It is a screening model, not a bird survey.

No local bird observations or mark-recapture data are bundled. The output labels every
bird result with its evidence tier and does not claim density or site-specific survival.

## Acceptance evidence

| Criterion | Status | Evidence |
| --- | --- | --- |
| Scenario returns habitat metrics and relative abundance with uncertainty | met with limit | `/api/birds`, Birds tab, 5 guilds |
| Demographic projection returns survival curve and lambda with intervals | met | two-stage matrix, prior range, survival curve |
| UI labels evidence and does not imply site-specific survival | met | prior badges and caveat text |
| Expert review is recorded | met with limit | expert-review request recorded; no review response yet |
| Dashboard green | met | dashboard GREEN; see verification |

## What was implemented

- `habitat.py`: live-tree structure, native share, mean/p95 height, raster cover/gap,
  vertical complexity, foliage-height diversity, layering, size diversity, composite
  habitat score, five guilds, suitability, relative-abundance index, optional CSV loader.
- `demography.py`: juvenile/adult matrix, lambda, prior range, survival curve, stable adult
  fraction, numerical sensitivity.
- `GET /api/birds`: baseline and scenario response.
- `fresh-urban-forest birds`: baseline or scenario JSON report.
- **Birds tab**: habitat metrics, guild bars, guild selector, lambda/prior range,
  sensitivity, adult survival chart, evidence badge.
- Docs and method note.

## Baseline demo result

UBC core demo:

- habitat score **0.78**
- p95 height **31.3 m**
- foliage-height diversity **0.61**
- layers **4**
- gap fraction **19%**
- native share **26%**

| Guild | Suitability | Relative index | Lambda | Prior range |
| --- | ---: | ---: | ---: | ---: |
| Canopy insectivores | 0.59 | 7.1 | 0.91 | 0.77–1.04 |
| Cavity nesters | 0.53 | 2.6 | 0.90 | 0.76–1.03 |
| Ground foragers | 0.38 | 3.4 | 0.82 | 0.70–0.94 |
| Migrants | 0.56 | 3.9 | 0.78 | 0.66–0.90 |
| Urban adapters | 0.34 | 6.7 | 1.09 | 0.92–1.25 |

The point lambda is not the claim. The prior range is the honest output.

## Scenario example

Selecting a Pareto 30-year scenario changed the demo habitat score to **0.62**, with p95
height 37.7 m, foliage diversity 0.38, and 3 layers. The Birds tab reloads when the
scenario preview changes.

That is a model response, not evidence that a real bird population will change.

## What was not validated

- No local point-count or eBird calibration.
- No distance sampling or detection correction.
- No mark-recapture, resighting, or nest data.
- No species-level habitat thresholds.
- No expert review response yet.
- No claim that a scenario causes a population change.

## Expert review request

Review requested from a UBC bird ecologist / urban ecology collaborator:

1. Are the five guilds and structural weights defensible?
2. Which local species should be added or removed?
3. Is the relative-abundance index useful as a screening aid?
4. What minimum field design would support a local survival estimate?

No response is recorded yet. This is a stated limit, not a completed review.

## Risks

- A unitless relative index can be mistaken for density.
- Prior-driven lambda can look more precise than it is.
- Structural metrics do not capture nest cavities, predators, noise, or connectivity.
- Scenario changes can be driven by one structural component.
- Sensitive bird locations must not be published without permission.

## Next phase

P11 integrates P7-P10, writes the v0.3 benchmark, and queues the release candidate.

No tag or release is created by this phase.
