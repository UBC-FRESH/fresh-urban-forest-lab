# P8 close-out: optimization and Pareto explorer

Date: 2026-11-03
Phase: P8
Parent issue: #41
Branch: `feature/p8-optimize-pareto`
Implementation head: `322c665`
Status: ready for review

## Summary

P8 turns the planting advisor into a multi-objective search. It delegates hard
combinatorial search to **Fresh Solutions** v0.8.0, the lab's hybrid metaheuristic engine.
This project supplies:

- the urban-forest problem adapter (site/species assignment);
- seven objectives and three constraints;
- a deterministic weighted-scalarisation grid;
- exact objective evaluation for every returned assignment;
- a feasible non-dominated archive with Monte Carlo hypervolume and bootstrap robustness;
- a 3D orbitable solution-space explorer and load-as-scenario path.

It does not implement a custom metaheuristic engine. It does not claim exact Pareto
optimality or city-scale performance.

## Acceptance evidence

| Criterion | Status | Evidence |
| --- | --- | --- |
| A 100-site, 5-species, 20-year problem with four-plus objectives solves end to end | met with limit | 48-site, 6-species, 20-year run completed; the UI defaults to 24 sites for laptop runs |
| Archive is non-dominated, reproducible from a seed, and carries uncertainty | met | `build_archive`, same seed/worker archive IDs, robustness in archive |
| UI can orbit, slice, brush, and load a solution as a scenario | met | Optimize tab, Three.js point cloud, slice controls, load-as-scenario browser check |
| Benchmark reports hypervolume, runtime, and surrogate error | met | tables below |
| Dashboard green | met | see verification |

## Search method

Fresh Solutions is a scalar solver. P8 runs a grid of weighted scalarisations:

1. one-hot objective weights;
2. a balanced weight vector;
3. seeded Dirichlet samples over the seven-objective simplex.

Each scalarisation runs `run_hybrid_search` (population search plus exact local
refinement). The main process evaluates every returned assignment with the exact
urban-forest evaluator and merges feasible results into the archive. Scalarisation jobs are
parallelised with spawned process workers.

The archive keeps only feasible, non-dominated solutions. Hypervolume is Monte Carlo
(20,000 samples) because seven dimensions are too high for a simple exact calculation.
Robustness is a 12-sample bootstrap.

## Benchmark

### Laptop-scale run (UBC core demo)

Problem: 24 sites, 6 species, 7 objectives, 20-year horizon, budget CAD 60,000.
Search: 18 scalarizations, population 20, 5 generations, 120 local iterations.

| Workers | Runtime | Evaluations | Archive | Hypervolume |
| --- | --- | --- | --- | --- |
| 1 | 0.332 s | 4,338 | 13 | 0.0106 |
| 2 | 1.110 s | 4,338 | 13 | 0.0106 |
| 4 | 1.159 s | 4,338 | 13 | 0.0106 |

For a tiny problem, spawned-worker startup dominates. The archive and hypervolume are
identical to the single-worker run.

### Larger run

Problem: 48 sites, 6 species, 7 objectives, 20-year horizon, budget CAD 120,000.
Search: 72 scalarizations, population 24, 8 generations, 300 local iterations.

| Workers | Runtime | Evaluations | Archive | Hypervolume |
| --- | --- | --- | --- | --- |
| 1 | 5.081 s | 37,224 | 56 | 0.051 |
| 4 | 3.573 s | 37,224 | 56 | 0.051 |

Parallel speedup: **1.42x** at four workers. Same seed, same archive solution IDs. This is
a laptop-scale result, not a city-scale claim.

### Surrogate

A 64-sample ridge surrogate was fitted on aggregate site/species features. Holdout
(13 samples):

| Objective | RMSE | R2 |
| --- | --- | --- |
| Shade | 21,704 m²h | 0.910 |
| Equity | 22,854 m²h | 0.864 |
| Native share | 0.058 | 0.889 |
| Diversity | 0.261 | -0.405 |
| Carbon | 0.0007 kg | 1.000 |
| Cost | 0.184 CAD | 1.000 |
| Water | 0.226 L | 1.000 |

The surrogate is a screening aid, not the archive evaluator. Its diversity error is poor
on this design, which is why the archive always uses exact evaluation.

### Toy archive

`tests/test_pareto.py` builds a two-objective archive with two known tradeoff points and
one dominated point. It checks dominance directions, non-dominated filtering, hypervolume
bounds, robustness bounds, and slice filtering. It is a correctness test, not a proof of
front convergence.

## Browser check

Headless Chromium at 1500 x 950:

- Optimize tab loads and runs a 16-site, 8-scalarisation, 2-generation job;
- archive renders as a 3D point cloud;
- X/Y/Z, colour, size, and slice controls work;
- selecting a point shows its objective vector and robustness;
- **Load selected as scenario** creates a scenario and previews it;
- no console errors.

Screenshots are retained locally under `tmp/screens/p8-optimize-final.png`; the public
docs use `docs/_static/pareto-explorer.png`.

## What was not validated

- No proof of Pareto optimality.
- No city-scale runtime claim.
- No full daily simulation for every candidate; the evaluator uses precomputed P7 values.
- No field validation of the selected plan.
- No external solver comparison beyond Fresh Solutions' own exact evaluator.
- Hypervolume is Monte Carlo; robustness is a bootstrap diagnostic.

## Risks carried forward

- Weighted-sum scalarisation can miss non-convex parts of the front.
- The archive is a finite sample; a larger scalarisation grid may find better tradeoffs.
- Spawned workers add overhead on small problems.
- The 3D explorer is a projection of seven objectives into three axes; the projection loss
  is shown by the axis/colour/size selectors but not quantified in a separate chart.
- The UI uses a small default site count for responsiveness.

## Next phase

P9 should add the off-inventory/private-canopy layer and run the value-of-information test
against this solver. The P8 archive and scenario path are the decision surface for that
test.

No tag or release is created by this phase.
