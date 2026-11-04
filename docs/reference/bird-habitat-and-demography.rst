Bird habitat and demography
===========================

P10 links 3D canopy structure to guild-level bird habitat, a relative-abundance index, and
a prior-driven demographic projection.

It is a screening model, not a bird survey or a local population forecast.

Three quantities
----------------

Keep these separate:

- **relative abundance index**: a unitless screening score, not birds per hectare;
- **density**: birds per unit area, requiring distance sampling or a calibrated model;
- **survival / lambda**: demographic rates and population growth, requiring local
  mark-recapture or resighting data for a site-specific estimate.

The built-in model provides the first and a prior version of the third. It does not provide
the second.

Habitat metrics
---------------

The structural layer uses:

- live-tree count and native share;
- mean and p95 height;
- raster canopy cover and gap fraction;
- vertical complexity;
- foliage-height diversity across 0–2, 2–5, 5–10, 10–15, 15–20, and 20+ m bands;
- layering count;
- DBH size diversity;
- a weighted composite habitat score.

Guilds
------

The priors cover canopy insectivores, cavity nesters, ground foragers, migrants, and urban
adapters. Each guild has a canopy/native/gap weight, a relative-abundance coefficient, and
juvenile/adult survival and fecundity priors.

A guild result contains:

- suitability from zero to one;
- a relative-abundance index;
- limiting structural factors;
- an evidence tier.

Demography
----------

The demographic layer is a two-stage matrix:

.. code-block:: text

   J(t+1) = fecundity * A(t)
   A(t+1) = juvenile_survival * J(t) + adult_survival * A(t)

It reports:

- lambda;
- low/base/high prior lambda range;
- adult survival curve;
- stable adult fraction;
- numerical sensitivity to fecundity, juvenile survival, and adult survival.

The projection is labelled ``prior`` until local demographic data exist.

Baseline demo
-------------

UBC core demo:

- habitat score **0.78**
- p95 height **31.3 m**
- foliage-height diversity **0.61**
- layers **4**
- gap fraction **19%**
- native share **26%**

Guild results:

.. list-table::
   :header-rows: 1

   * - Guild
     - Suitability
     - Relative index
     - Lambda
     - Prior range
   * - Canopy insectivores
     - 0.59
     - 7.1
     - 0.91
     - 0.77–1.04
   * - Cavity nesters
     - 0.53
     - 2.6
     - 0.90
     - 0.76–1.03
   * - Ground foragers
     - 0.38
     - 3.4
     - 0.82
     - 0.70–0.94
   * - Migrants
     - 0.56
     - 3.9
     - 0.78
     - 0.66–0.90
   * - Urban adapters
     - 0.34
     - 6.7
     - 1.09
     - 0.92–1.25

These are priors. The range, not the point estimate, is the honest output.

API and CLI
-----------

.. code-block:: bash

   fresh-urban-forest birds \
     --dataset data/demo/ubc_core \
     --out tmp/birds.json

   fresh-urban-forest birds \
     --dataset data/demo/ubc_core \
     --scenario runtime/scenarios/<id>.json \
     --year 25 \
     --out tmp/scenario-birds.json

- ``GET /api/birds`` returns baseline habitat, guild, and demographic results.
- ``GET /api/birds?scenario_id=<id>&year=<year>`` returns a scenario result.
- The Birds tab shows structural metrics, guild bars, lambda/prior range, sensitivity, and
  an adult survival curve.

.. image:: /_static/birds.png
   :alt: Bird habitat, guild, and prior demographic view
   :width: 100%

Limits
------

- No local bird survey or mark-recapture data are bundled.
- Guild coefficients are priors, not fitted Vancouver parameters.
- The relative index is not density.
- Lambda is a screening projection, not a forecast.
- A scenario change is a model response, not evidence that a real population will change.
- An expert review and local observations are still required.

The method note is ``notes/reference/bird-habitat-methods.md`` and the phase report is
``notes/reports/p10-birds.md``.
