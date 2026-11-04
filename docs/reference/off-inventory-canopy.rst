Off-inventory canopy
====================

Official inventories miss trees. Some are on private property, some are in parks or
natural areas, and some are simply not surveyed. P9 adds a separate **off-inventory
urban-tree** candidate layer and tests whether including it changes the baseline canopy
and the planting decision.

A scenario is one plan. An off-inventory candidate is one unmatched LiDAR crown. Neither
is a confirmed private tree.

Terminology
-----------

Use **off-inventory urban trees** for the operational layer. Use
**private-property canopy** when ownership is the point. Use **trees outside forests
(TOF)** only under the FAO/forest-inventory definition.

“Shadow urban forest” is a nickname, not a scientific term. “Shadow inventory” already
means off-market housing in real estate.

Method
------

1. Detect crowns from a CHM patch with local maxima and marker-controlled watershed.
2. Match detected crowns to live official inventory trees with the documented greedy
   nearest rule and tolerance.
3. Keep unmatched crowns as candidates.
4. Score each candidate from height, crown size, distance to the nearest official tree,
   and land class.
5. Keep the candidate layer separate from the official inventory.

A candidate carries:

- stable ``off:<id>`` identity;
- detected height and crown radius;
- nearest official-tree distance;
- inferred land class;
- a confidence score and human-readable reasons.

The pilot has no parcel layer, so every land class is **ownership unknown**. It is a proxy,
not legal title.

Privacy
-------

Public outputs are aggregate or candidate-level. No owner names, addresses, private
photos, or parcel-level ownership claims are stored or exposed. A private-property field
pilot needs a written access and data-sharing agreement.

API and CLI
-----------

.. code-block:: bash

   fresh-urban-forest off-inventory \
     --dataset data/processed/ubc_lidar_2021 \
     --chm data/raw/ubc/lidar_2021/CHM_1m.tif \
     --bbox=-123.255,49.258,-123.245,49.265 \
     --window 4 \
     --max-distance 4 \
     --grid-size 700 \
     --out-dir data/demo/ubc_core \
     --voi

Endpoints:

- ``GET /api/off-inventory``: summary and candidates.
- ``GET /api/off-inventory.geojson``: public candidate points.
- ``GET /api/off-inventory/value``: value-of-information comparison.

The demo dataset ships a Main Mall pilot layer in ``off_inventory.json``,
``off_inventory.geojson``, and ``off_inventory_voi.json``. The web map has an
**off-inventory** layer toggle and a sidebar summary. The layer is off by default.

.. image:: /_static/off-inventory.png
   :alt: Off-inventory candidate layer and sidebar summary
   :width: 100%

Pilot result
------------

Main Mall patch, UBC 2021 CHM, 700-cell detection grid, confidence >= 0.3, capped at 500
candidates:

- 5,536 detected crowns
- 1,409 one-to-one inventory matches
- 500 candidates (the cap)
- 435 candidates at confidence >= 0.6
- 8.3 ha of candidate crown area
- all candidates inside the analysis boundary; ownership unknown

The 500-candidate cap is a screening limit, not a census.

Value of information
--------------------

The P8 solver was run on the official population and on the official + candidate
population with the same site count, budget, horizon, and seed.

.. list-table::
   :header-rows: 1

   * - Metric
     - Official
     - Augmented
   * - Live-tree count
     - 9,259
     - 9,759
   * - Crown volume
     - 2.855M m³
     - 3.669M m³
   * - Above-ground carbon
     - 3,827 t
     - 5,024 t
   * - Best-shade archive solution
     - 101,149 m²h
     - 101,149 m²h
   * - Archive size
     - 7
     - 7
   * - Best-shade plan Jaccard
     - —
     - 1.00
   * - Changed sites
     - —
     - 0

The candidate layer changes the **baseline canopy accounting** substantially, but it did
not change the best-shade planting plan in this pilot. The candidates are concentrated in
already-shaded Main Mall canopy, so they do not change the sampled sun fraction at the
candidate planting sites.

That is a useful result: the value of the layer can be in measurement and habitat
accounting even when the planting recommendation is stable.

Limits
------

- No parcel layer, so ownership is unknown.
- No completed field reference patch; candidates are not verified.
- The 500-candidate cap and confidence threshold are screening choices.
- The coarse detection grid and matching tolerance affect candidate counts.
- The augmented carbon/canopy totals depend on unknown species and allometry.
- The value-of-information comparison is a finite solver comparison, not a field result.

The method and privacy note is ``notes/reference/off-inventory-terminology.md``.
The phase report is ``notes/reports/p9-off-inventory.md``.
