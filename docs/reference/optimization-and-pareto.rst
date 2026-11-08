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

Inspection, filters, and sharing
--------------------------------

The P47 explorer refresh adds:

- a hover tooltip with the solution id and objective values;
- selected and reference markers in the 3D cloud, with objective deltas against the
  reference;
- actual ideal/nadir ranges for the mapped axes;
- a **robustness floor** that filters solutions by their bootstrap robustness score;
- synchronized parallel coordinates for the filtered archive;
- clickable parallel lines that select the same solution as the 3D view;
- single-axis brushes and Shift-drag multi-axis brushes, with removable chips;
- a copy-view link, filtered CSV export, and URL state for axes, floor, point, reference,
  brushes, and preset name;
- a local **Saved views** panel with save/load/delete, versioned JSON export/import, and a
  portable preset link.

The parallel axes are built from the archive objectives plus robustness, planted-site
count, and habitat. Cost and water axes fall back to metrics only when the archive does
not expose them as objectives. Brushes combine with AND and filter the 3D cloud, parallel
lines, and CSV together.

Local views are stored in the browser, not on the server. Imported libraries are
versioned and validated. A view records its archive/job id and is refused when the current
archive does not match, rather than silently applying to a different front.

P47.4, a server-backed shared review library with self-declared author/note and
``draft``/``reviewed`` metadata, is **not implemented** in this phase. There are no
accounts, permissions, verified reviews, or server-shared views. The local library remains
the supported path.

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
appears in the dropdown. Archives can be renamed or deleted from the panel. The panel shows
the dataset, horizon, budget, site cap, and save date.

Selecting a scenario named ``Pareto <solution>`` from the header jumps back to its source
archive and highlights that point in the front. Pin up to three solutions to compare their
objective vectors in a compact table.

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
- ``GET /api/optimize`` lists jobs and saved archives.
- ``GET /api/optimize/{job}`` returns status and the full result.
- ``GET /api/optimize/{job}/solutions`` returns the archive.
- ``PATCH /api/optimize/{job}`` renames a saved archive.
- ``DELETE /api/optimize/{job}`` deletes a saved archive.
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
- The robustness floor is a bootstrap diagnostic, not a quality or feasibility guarantee.
- Parallel brushes are viewer filters, not optimizer constraints or proof that a
  solution is implementable.
- Local saved views are browser-local and archive-specific; clearing browser storage
  removes them. They are not a shared review record.
- A copied preset link carries the viewer state but still needs the referenced saved
  archive to be available on the server that opens it.

The benchmark and method report are in ``notes/reports/p8-optimization-pareto.md``.
