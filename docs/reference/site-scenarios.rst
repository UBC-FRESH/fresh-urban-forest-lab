Site-level planting scenarios
=============================

P48 adds a bounded site-level scenario layer on top of the P39 canopy-gap screen and the
P42/P44 action screen. It is a **scenario screen**, not a planting plan, ownership record,
survival forecast, or field-validated recommendation.

What the layer does
-------------------

- Extracts contiguous candidate sites from P39 gap components.
- Joins P42/P44 action labels as context only.
- Places hypothetical trees with explicit species, height, crown radius, tree count,
  cost, water, and maintenance assumptions.
- Evaluates baseline and scenario shade with the existing projected-shadow model on the
  same time samples, target height, step, and terrain setting.
- Reports total and per-site combined shade area-hours, shade fractions, percent deltas,
  and optional height/crown sensitivity.
- Lets a user open the selected hypothetical trees in the existing 3D scene as a normal
  scenario.

What it is not
--------------

- Not a private-tree census or confirmed ownership layer.
- Not a permit, access, utility, soil, irrigation, or maintenance assessment.
- Not evidence that a candidate site is plantable.
- Not a tree-survival, cooling, causal, or field-validation study.
- Not a citywide canopy-change claim. P45's citywide net direction remains unresolved.

Candidate sites
---------------

The candidate build uses the P39 gap masks at 5 m and extracts contiguous edge-gap
components at least 45 m². It keeps the largest components per 400 m cell and applies a
global cap. P42/P44 action labels and opportunity tiers are joined by cell id.

Vancouver build output is under ``data/processed/vancouver_2022/``:

- ``site_candidates.json``
- ``site_candidates.geojson``
- ``site_candidates_meta.json``

The deterministic build command is:

.. code-block:: bash

   python scripts/build_vancouver_site_candidates.py \
     --root data/processed/vancouver_2022 \
     --out data/processed/vancouver_2022 \
     --resolution 5 \
     --cell-size 400 \
     --site-min-area 45 \
     --max-sites 5000 \
     --max-sites-per-cell 12

Candidate records have no owner, address, parcel, or permit fields. The candidate layer is
an above-ground screen; a gap is not permission to plant.

Scenario contract
-----------------

The schema is ``fresh-urban-forest.site-scenario.v1``. A scenario contains:

- a stable scenario id and label;
- shared evaluation settings;
- up to 200 sites;
- up to 1,000 trees in total;
- per-site species, height, crown radius, count, cost, water, maintenance, and
  assumption source;
- derived site, tree, cost, and water totals;
- optional metrics, uncertainty, and caveats.

Duplicate site ids, unknown candidate ids, out-of-range values, and oversized scenarios
are rejected. The contract is implemented in :mod:`fresh_urban_forest.site_scenario`.

Shade evaluation
----------------

The evaluator in :mod:`fresh_urban_forest.site_shade` adds hypothetical trees at candidate
coordinates and runs the projected-shadow accumulation model. Baseline and scenario use
the same samples and target height. Cost and water assumptions are carried separately from
the shade result.

The output method label is ``projected-shadow-accumulation-combined``. The result is a
2.5-D projected-shadow screen; it does not model penumbra, leaf transmissivity, facade
geometry, survival, or temperature.

The two-site pilot used one 2026-06-21 12:00 PDT sample, two ``plant + cool`` sites, and
8 m height / 3 m crown-radius assumptions. Baseline combined shade was
**35,752,669.3 m²h**; the scenario added **1,158.34 m²h (+0.0032%)**. Per-site contributions
were **579.17 m²h** each. Height/crown ±20% cases ranged from **868.75 to 1,737.51 m²h**.
This is one sample, not annual shade.

Sites tab
---------

The **Sites** tab:

- loads the optional candidate GeoJSON;
- colours points by action class;
- lets the user click sites on or off;
- offers a six-site ``plant + cool`` quick-select;
- applies shared assumptions to selected sites;
- evaluates baseline and scenario shade;
- shows per-site and optional sensitivity tables;
- can open the selected trees in the 3D scene as a normal scenario.

The map and scenario are viewer screens. No ownership or permit inference is made.

API
---

- ``GET /api/site-candidates``
- ``GET /api/site-candidates.geojson``
- ``POST /api/site-scenario/evaluate``

The evaluate request contains a validated scenario, one to 24 ISO sample times, target
height, terrain flag, per-site flag, and sensitivity flag. Responses include the normalized
scenario and baseline/scenario evaluation.

Limits
------

- Candidate capacity is an upper bound, not a planting target.
- Road-adjacent is a proxy, not a confirmed boulevard or planting strip.
- Utilities, ownership, access, soil, irrigation, and maintenance are not modelled.
- Shade is a projected surface, not measured cooling or thermal comfort.
- A one-sample pilot is not annual shade.
- P45's citywide change direction remains unresolved.
- No field validation, survival, causal, or operational recommendation is claimed.
