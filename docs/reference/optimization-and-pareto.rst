Optimization and the Pareto explorer
====================================

P8 turns the planting advisor into a multi-objective search. It does not invent a new
metaheuristic. Hard combinatorial search is delegated to
`Fresh Solutions <https://github.com/UBC-FRESH/fresh-solutions>`_, the lab's hybrid
metaheuristic engine. This project supplies the urban-forest problem adapter, the weighted
scalarisation grid, exact objective evaluation, the archive, and the browser explorer.

Problem
-------

A problem has:

- a set of candidate sites from the planting advisor;
- one species option per site, plus an empty option;
- objectives for effective shade, shade equity, native share, species diversity, carbon,
  cost, and irrigation water;
- constraints for maximum planted sites, budget, and maximum species share;
- a projection horizon and a search seed.

The schema is in :mod:`fresh_urban_forest.optimize`. It round-trips through JSON and is
exposed by the CLI, the API, and the archive.

Search
------

Fresh Solutions is a scalar solver: it minimises one exact objective at a time. P8
therefore solves a **grid of weighted scalarisations**:

1. build one-hot, balanced, and Dirichlet weight vectors over the objectives;
2. normalise each objective by a transparent scale;
3. run Fresh Solutions population search plus exact local refinement for each weight;
4. evaluate every returned assignment with the exact urban-forest evaluator;
5. merge the feasible results into a non-dominated archive.

The scalarisations run in parallel process workers. The same seed and weight grid produce
the same archive.

This is the "many optimization problems" step. It is deliberately not a claim that the
weighted-sum grid recovers every Pareto-optimal solution. It is a reproducible finite
approximation.

Archive and uncertainty
-----------------------

The archive:

- keeps only feasible, non-dominated solutions;
- reports ideal/nadir values;
- estimates normalized hypervolume by Monte Carlo;
- bootstraps a robustness score for every solution;
- attaches the exact objective vector and planted-site list.

A solution with high robustness stays on the front under small objective perturbations.
It is still an approximation, not a proof.

Web explorer
------------

The **Optimize** tab:

- starts a background job with site, scalarisation, population, generation, worker, and
  budget controls;
- polls job progress;
- renders the archive as an orbitable 3D point cloud;
- lets the user choose X, Y, Z, colour, size, and a slice objective;
- filters the cloud with a slice threshold;
- selects a solution and shows its objective vector and robustness;
- loads the selected solution as a scenario.

The viewer uses vendored Three.js and `OrbitControls`; there is no external service.

Saved runs and scenarios
------------------------

A **scenario** is one tree population. A **Pareto archive** is the population of
non-dominated solutions from one optimization run. They are different objects.

Completed optimization jobs are written to:

.. code-block:: text

   runtime/optimizations/<job_id>.json

On startup, every JSON file in that directory is loaded as a completed job. The
**Saved Pareto archive** dropdown in the Optimize tab lists those jobs with their archive
size and hypervolume. Select one and press **Load saved archive** to view the front again
without re-running the solver. Then click a sphere and **Load selected as scenario** to
turn one solution into a scenario.

A saved archive can also be produced outside the browser. For example:

.. code-block:: bash

   fresh-urban-forest optimize --dataset data/processed/ubc_lidar_2021 \
     --out runtime/optimizations/full-campus-387.json \
     --sites 387 --max-sites 387 --horizon 30 --budget 8000000 \
     --scalarizations 72 --population 40 --generations 100 \
     --local-iterations 10000 --workers 8

Restart the service, or refresh the Optimize tab after the job finishes, and the archive
appears in the dropdown.

.. image:: /_static/pareto-explorer.png
   :alt: Optimize tab with an orbitable Pareto archive and a selected solution
   :width: 100%

API and CLI
-----------

.. code-block:: bash

   fresh-urban-forest optimize \
     --dataset data/demo/ubc_core \
     --out tmp/optimization.json \
     --sites 24 \
     --scalarizations 18 \
     --population 20 \
     --generations 5 \
     --workers 2

   fresh-urban-forest pareto \
     --archive tmp/optimization.json \
     --out tmp/pareto-summary.json

Endpoints:

- ``POST /api/optimize`` starts a job.
- ``GET /api/optimize`` lists jobs.
- ``GET /api/optimize/{job}`` returns status and the full result.
- ``GET /api/optimize/{job}/solutions`` returns the archive.
- ``POST /api/optimize/{job}/scenario`` loads a solution as a scenario.

The optimizer is an optional extra:

.. code-block:: bash

   python -m pip install -e ".[optimize]"

It installs Fresh Solutions from its tagged repository. The rest of the lab still runs
without the extra.

Limits
------

- Weighted scalarisation is a finite approximation of the Pareto front.
- Hypervolume is Monte Carlo, not exact for seven objectives.
- Robustness is a bootstrap diagnostic, not a dominance proof.
- The fast evaluator uses precomputed P7 shade/water/carbon/habitat values; it is not a
  full daily scenario simulation for every candidate.
- The default candidate grid is small enough for a laptop. City-scale coverage needs a
  larger data and compute budget.
- The surrogate is a screening aid. The archive always uses the exact evaluator.

The benchmark and method report are in ``notes/reports/p8-optimization-pareto.md``.
