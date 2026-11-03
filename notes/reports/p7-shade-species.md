# P7 close-out: solar shade, species fit, water, and irrigation

Date: 2026-11-03
Phase: P7
Parent issue: #40
Branch: `feature/p7-shade-species`
Implementation head: `8849e56`
Pull request: #53
Status: ready for review

## Summary

P7 adds a tree-level light and water layer to the lab. It computes solar position, casts
building/tree/terrain shadows, accumulates shade over time, and separates the marginal
shade caused by a selected tree from shade already provided by buildings and other trees.
It then couples that light regime to a species trait fit, a daily soil-water balance,
growth/vigour modifiers, and irrigation cost.

The key product is **marginal effective shade**, not canopy cover. A tree in deep building
shade or a closed canopy can have a large crown and a marginal shade value near zero. That
is the intended result, not a bug.

## Acceptance evidence

| Criterion | Status | Evidence |
| --- | --- | --- |
| Date/time request returns a georeferenced shadow raster and metrics | met | `GET /api/shade`, `GET /api/shade.png`; `tests/test_service.py`; `tests/test_shade.py` |
| Full-year aggregate returns seasonal/annual shade-hours with uncertainty | met with limit | `mode=annual` samples 12 months x 4 times; annual estimate is a scaled sample, not a full hourly year |
| Tree card separates building, canopy, and marginal tree shade | met | `GET /api/light/tree/{id}`; `shade_at_tree`; UI tree-light card |
| Species list ranked by site fit with limiting factors and evidence tiers | met | `fresh-urban-forest species-fit`; `/api/species/fit`; `tests/test_species.py` |
| Water/irrigation card gives stress days and a cost range | met with limit | `compare_water_policies`, `compare_irrigation`; default climate is illustrative |
| Dashboard green and docs describe method and limits | met | dashboard GREEN; `docs/reference/shade-and-species.rst` |

## What was implemented

- `solar.py`: NOAA solar position, sunrise/sunset, daylight hours, daily and annual time
  grids, timezone handling.
- `shadow.py`: projected building footprints, ellipsoidal tree crowns, target-height
  plane, optional coarse terrain horizon, mode-specific PNG masks.
- `shade.py`: time-integrated sunlit/building/tree/terrain/overlap/marginal arrays,
  effective-shade fractions, annual estimate, tree shade card, product writer.
- `species.py`: 12 species profiles plus conifer/deciduous/unknown fallbacks; light, water,
  soil, heat, and space fit; limiting factors.
- `water.py`: single-bucket daily water balance; none/establishment/fixed/moisture-trigger/
  deficit policies; water, labour, and annual cost.
- `vigor.py`: light/water/heat/soil/competition growth modifiers; vigour score; 20-year
  species projection.
- `irrigation.py`: policy ranking and cost per effective shade-hour.
- `evidence.py`: measured/physics/calibrated/scenario/prior tiers.
- API: `/api/solar`, `/api/shade`, `/api/shade.png`, `/api/light/tree/{id}`,
  `/api/species`, `/api/species/fit`, `/api/water`, `/api/irrigation`.
- CLI: `shade`, `species-fit`, `water`, `irrigation`.
- UI: **Light** tab with date/time/period controls, georeferenced shadow overlay, 3D sun,
  legend, tree shade/water card, evidence badges.
- Docs: `docs/reference/shade-and-species.rst`, API reference, `llms.txt`.
- Tests: 268 total, including solar geometry, shadow geometry/direction, shade
  conservation, marginal shade, species fit, water policy ordering, vigour, irrigation,
  service endpoints, CLI, and static shell hooks.

## Validation

### Solar position

The solar-noon test for Vancouver on 2026-06-21 returns:

- solar noon: `2026-06-21T13:14:19-07:00`
- altitude: `64.194°`
- azimuth: `179.954°`

This is consistent with the solstice geometry (90 - |49.26 - 23.44| = 64.18°). Tests cover
summer/winter daylight, night, timezone-aware grids, and the solar-noon altitude range.

### Shadow geometry

Tests cover:

- building and tree masks are non-empty and separable;
- combined is the union of the three sources;
- a low sun casts a larger building shadow than a near-overhead sun;
- a higher target plane shortens the building shadow;
- excluding a tree reduces the tree count and mask;
- night produces empty direct-shadow masks;
- all PNG modes are valid.

### Time-sampling sensitivity (UBC core demo, 2026-06-21)

| Sample | Sunlit | Shade | Building | Tree | Marginal tree | Annual estimate |
| --- | --- | --- | --- | --- | --- | --- |
| 3 times (09, 12, 15) | 93.18% | 6.82% | 6.20% | 2.54% | 0.50% | 399 h |
| 6 times (08, 10, 12, 14, 16, 18) | 92.77% | 7.23% | 6.31% | 2.54% | 0.51% | 423 h |

The combined shade fraction changes by about 0.41 percentage points (6% relative) when
the sampling doubles; tree and marginal-tree fractions are stable. The annual estimate
changes with sampling and must be read as a sample estimate.

Target-height sensitivity at 19:00 UTC:

| Target height | Building cells | Tree cells | Combined cells |
| --- | --- | --- | --- |
| 0.1 m | 1,640 | 681 | 1,799 |
| 1.5 m | 1,639 | 684 | 1,797 |
| 5.0 m | 1,584 | 689 | 1,751 |

### Browser check

The Light tab was checked in headless Chromium at 1500 x 950:

- shadow overlay and legend render;
- the date/time controls and period selector load;
- the 3D scene shows the sun at `60° / 144°` for 2026-06-21 12:00;
- selecting a tree shows the shade/species/water card;
- no console errors.

Screenshots are retained locally under `tmp/screens/p7-light.png`,
`tmp/screens/p7-tree-light.png`, and `tmp/screens/p7-scene-sun.png`; they are not tracked.

## What was not validated

- No field shade survey or orthophoto shadow measurement was completed.
- No Radiance or SOLWEIG benchmark was run. That comparison is the next validation step.
- Facade and roof target sampling are not exposed; the kernel is tuned for the 1.5 m
  pedestrian plane.
- Penumbra, leaf transmissivity, wind, and CFD are not modelled.
- Species traits are expert priors; they are not local trial results.
- The default climate is an illustrative monthly series, not a TMY.
- Growth is not calibrated to repeat measurements. It is a scenario/prior projection.
- Irrigation cost is a planning estimate, not a utility bill.

## Risks and limits carried forward

- The annual estimate is a scaled representative sample, not a full hourly year.
- A marginal-shade zero can mean the tree is fully inside existing shade; it does not mean
  the tree has no ecological value.
- Building and tree overlap is counted once in the combined total but is visible separately.
- The UI uses the coarse dataset terrain grid; a 1 m shade product would need a larger
  compute budget.
- The terrain horizon is coarse and only evaluated for small grids.

## Next phase

P8 should use the P7 shade/species evaluator as the objective layer:

1. define the decision variables, objectives, and constraints;
2. add the fast evaluator and surrogate;
3. implement the parallel solver and fuzzy Pareto archive;
4. add the 3D solution-space explorer;
5. benchmark against a toy front and the campus scenario.

Do not tag or release P7. The phase PR and parent issue close after maintainer approval.

## Dashboard

`python scripts/dashboard.py` is GREEN:

- lint, format, strict types, tests, workflow validator, and docs all pass.
- `268 passed`.
