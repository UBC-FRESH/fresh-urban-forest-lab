Data contracts
==============

The typed contracts live in ``src/fresh_urban_forest/models.py``. They are frozen
dataclasses so a dataset cannot be mutated by accident.

Dataset directory
-----------------

A dataset directory contains:

.. list-table::
   :header-rows: 1

   * - File
     - Purpose
   * - ``manifest.json``
     - Dataset id, CRS, bounds, tree count, sources, metrics, and the file map.
   * - ``trees.json``
     - Normalised tree records.
   * - ``metrics.json``
     - Baseline canopy and composition metrics.
   * - ``terrain.npz``
     - Elevation and canopy-height arrays.
   * - ``terrain.json``
     - CRS, bounds, width, and height for the arrays.
   * - ``buildings.geojson``
     - Building footprints in WGS84.
   * - ``boundary.geojson``
     - Analysis boundary in WGS84.
   * - ``change.json`` (optional)
     - Observed-change summary: labels, threshold, metrics, legend, and overlap.
   * - ``change.png`` (optional)
     - Transparent loss/stable/gain overlay.
   * - ``change_grid.npz`` (optional)
     - Change classes, earlier/later canopy, elevation, and valid mask.

Tree record
-----------

Required: ``tree_id``, ``lon``, ``lat``. Optional but expected: ``species``,
``common_name``, ``dbh_cm``, ``height_m``, ``crown_width_m``, ``crown_ratio``,
``status``, ``source``, ``native``, ``x_m``, ``y_m``, ``elevation_m``, and
``lidar_height_m``.

Scenario
--------

A scenario is a base dataset id, an ordered tuple of edits, a projection horizon, and a
revision. An edit is one of ``plant``, ``remove``, ``replace``, or ``move``. The server
appends edits with a revision check and persists the scenario atomically.

Scene payload
-------------

The browser receives one payload with:

- ``origin`` and ``origin_lonlat``;
- ``meters_per_degree``;
- WGS84 and projected bounds;
- terrain arrays in row-major order;
- trees with both WGS84 and local metres;
- buildings with WGS84 and local rings;
- the boundary ring.

The same local origin is used by MapLibre and Three.js. A tree selected in either view is
the same record.

API
---

The service exposes ``/api/dataset``, ``/api/metrics``, ``/api/trees``, ``/api/scene``,
``/api/canopy.png``, ``/api/hillshade.png``, ``/api/scenarios``, scenario projection and
comparison routes, ``/api/dss/recommend``, and GeoJSON/CSV exports. The OpenAPI document
is available at ``/docs`` when the service is running.
