# P8 close-out: optimization and Pareto explorer

Date: 2026-11-03
Phase: P8
Parent issue: #41
Branch: `feature/p8-optimize-pareto`
Implementation head: `322c665` + UI QA follow-up
Benchmark evidence: `notes/reports/p8-benchmark-evidence.json`
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

All hypervolumes use a **fixed** problem-scale reference box. They are comparable across
archives of different sizes. They are not comparable to a different problem definition.

### Laptop-scale run (UBC core demo)

Problem: 24 sites, 6 species, 7 objectives, 20-year horizon, budget CAD 60,000, max 40 sites.
Search: 18 scalarizations, population 20, 5 generations, 120 local iterations.

| Workers | Runtime | Evaluations | Archive | Hypervolume |
| --- | --- | --- | --- | --- |
| 1 | 0.341 s | 4,338 | 13 | 0.0006 |
| 2 | 1.240 s | 4,338 | 13 | 0.0006 |
| 4 | 1.251 s | 4,338 | 13 | 0.0006 |

For a tiny problem, spawned-worker startup dominates. The archive and hypervolume are
identical to the single-worker run.

### Larger run

Problem: 48 sites, 6 species, 7 objectives, 20-year horizon, budget CAD 120,000.
Search: 72 scalarizations, population 24, 8 generations, 300 local iterations.

| Workers | Runtime | Evaluations | Archive | Hypervolume |
| --- | --- | --- | --- | --- |
| 1 | 5.340 s | 37,224 | 56 | 0.0014 |
| 4 | 3.638 s | 37,224 | 56 | 0.0014 |

Parallel speedup: **1.47x** at four workers. Same seed, same archive solution IDs.

### Whole-campus run

Dataset: `data/processed/ubc_lidar_2021` (9,324 tree records; 387 available planting
sites at 12 m spacing). Problem: 387 sites, 6 species, 7 objectives, 30-year horizon,
budget CAD 8,000,000, max 387 sites. Search: 72 scalarizations, population 40, 100
generations, 10,000 local iterations, 8 workers.

- Runtime: **100.94 s**
- Exact evaluations: **1,010,952**
- Archive: **71 non-dominated feasible solutions**
- Hypervolume: **0.0508**
- Planted-site range: **0 to 387**
- Top shade solutions plant 385 trees; the native-share extreme plants 386 trees with
  native share 1.0; the empty plan is the zero-cost/zero-water extreme.

This is a real whole-campus candidate set, not the 24-site demo.

Reproduce the archive with:

.. code-block:: bash

   fresh-urban-forest optimize \
     --dataset data/processed/ubc_lidar_2021 \
     --out tmp/full_campus.json \
     --sites 387 --max-sites 387 --horizon 30 --budget 8000000 \
     --scalarizations 72 --population 40 --generations 100 \
     --local-iterations 10000 --workers 8

### Z* convergence

Z* here means the best **balanced weighted-scalar objective** found by Fresh Solutions,
not a proof of global optimality. We used Fresh Solutions' `run_to_convergence` with
population 80, 500 generations, 2,000 local iterations per round, 8 patience rounds, and
a 1,000,000-evaluation cap.

Whole-campus problem (387 sites, max 387, budget CAD 8,000,000):

- Converged: **True** (stop reason: patience)
- Rounds: **36**
- Evaluations: **112,116**
- Runtime: **79.8 s**
- Best scalar objective: **-0.293285**
- Feasible: **True**, 333 planted sites
- Objectives: shade 21.05M m²h, equity 19.52M m²h, native 0.502, diversity 1.762,
  carbon 24,607 kg, cost CAD 5.09M, water 4.45M L

The last eight rounds improved the scalar objective from -0.292254 to -0.293285 before the
patience rule stopped the search. That is the observed plateau.

A second convergence check on the 40-site-constrained problem stopped at patience in
13 and 10 rounds for seeds 1 and 2, with best objectives -0.240911 and -0.239939. Both were
feasible and planted 40 sites. This shows the stopping rule is not a one-seed accident.

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

Headless Chromium at 1500 x 950 and 900 x 700:

- Optimize tab loads and runs 12-site / 6-scalarisation and 16-site / 8-scalarisation jobs;
- archive renders as a 3D point cloud;
- X/Y/Z, colour, size, and slice controls work;
- an actual canvas click selects a sphere and enables the load button;
- **Load selected as scenario** creates a scenario, selects it in the scenario dropdown, and
  previews it;
- completed jobs auto-save to `runtime/optimizations/` and reload through the **Saved
  Pareto archive** dropdown without re-running the solver, including the
  `full-campus-387` archive;
- selecting any scenario in the global dropdown from the Optimize tab switches to the 3D
  scene, so the loaded scenario is visible instead of leaving the user on an unchanged
  point cloud;
- the 3D terrain mesh now uses the same origin as trees and buildings, and DEM nodata is
  filled from the nearest valid cell, so the ground no longer appears as a shifted
  zero-elevation plane under floating objects;
- switching tabs during a run, resizing, and rapid tab switching produce no console or
  page errors;
- the slice slider and load button reset on a new run;
- no console errors, page errors, or failed requests.

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
