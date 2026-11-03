Validation and calibration
==========================

The prototype distinguishes four evidence levels:

1. **Measured** inventory attributes.
2. **Imputed** attributes from LiDAR or allometry.
3. **Detected** crowns from the CHM.
4. **Validated** crowns and attributes from a field reference patch.

Detection validation
--------------------

``fresh-urban-forest validate-detection`` matches detected crowns to inventory trees with
a greedy nearest rule, highest detected crown first, one inventory tree per detected
crown.

First UBC core run:

.. list-table::
   :header-rows: 1

   * - Metric
     - Value
   * - Detected crowns
     - 12,715
   * - Inventory trees
     - 4,861
   * - Matched
     - 2,764
   * - Precision
     - 0.217
   * - Recall
     - 0.569
   * - F1
     - 0.315
   * - Mean match distance
     - 2.26 m
   * - Height bias
     - +1.78 m
   * - Height RMSE
     - 5.04 m
   * - Crown-radius bias
     - +0.74 m

This is not a clean accuracy estimate: the inventory is incomplete, so an unmatched
detected crown may be a real tree. The detector also over-segments.

Tuning
------

A Main Mall patch was swept at 1 m. Best F1 was **0.366** at
``min-height=3``, ``window=6``. A wider window raises precision but loses recall. The
tuned full-core run produced 9,678 detected, 2,314 matches, precision 0.239, recall 0.476,
F1 0.318.

Field reference packet
----------------------

The route to a defensible precision estimate is a complete reference patch:

.. code-block:: bash

   fresh-urban-forest field-packet \
     --dataset data/processed/ubc_lidar_2021 \
     --chm data/raw/ubc/lidar_2021/CHM_1m.tif \
     --bbox -123.255,49.258,-123.245,49.265 \
     --min-height 3 \
     --window 6 \
     --max-trees 200 \
     --out-dir data/processed/field_packet_mainmall

The packet contains inventory trees, detected crowns, a tree checklist, a detected-crown
checklist, and a protocol.

After field work:

.. code-block:: bash

   fresh-urban-forest analyze-field-packet \
     --packet data/processed/field_packet_mainmall \
     --out-dir data/processed/field_packet_mainmall/analysis

The analysis reports precision, precision including merged crowns, recall, missing/new
trees, and height/crown bias. Only field-verified rows enter the metrics.

Local allometry
---------------

``fresh-urban-forest fit-allometry`` fits
``height = 1.3 + coefficient * DBH ** exponent`` from trees with measured DBH and height.

.. list-table::
   :header-rows: 1

   * - Group
     - n
     - Coefficient
     - Exponent
     - RMSE
     - R²
     - Generic RMSE
   * - Conifer
     - 1,313
     - 0.656
     - 0.823
     - 7.42 m
     - 0.342
     - 12.38 m
   * - Deciduous
     - 2,762
     - 0.695
     - 0.745
     - 4.87 m
     - 0.492
     - 7.18 m
   * - Unknown
     - 463
     - 0.791
     - 0.663
     - 3.03 m
     - 0.497
     - 7.16 m

The local fits reduce height RMSE versus the generic profiles, but they are **not** a
growth model.

Growth calibration gap
----------------------

The UBC inventory has 9,322 unique tree IDs and **zero** IDs with more than one
measurement date. There are 4,568 trees with measured DBH and height, but the data are
cross-sectional. Annual growth calibration is blocked by data, not code.

A future round needs:

- stable ``tree_id`` across rounds;
- ``measurement_id`` and ``measurement_date``;
- repeated DBH, height, crown width, crown base, condition, and crown light exposure;
- measured and imputed values stored separately;
- survey method and crew metadata.

Until then, the generic growth model is the scenario engine and must be labelled as a
scenario model, not a calibrated prediction.
