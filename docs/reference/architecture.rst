Architecture
============

The system is a typed Python core, a portable dataset directory, a FastAPI service, and a
vanilla JavaScript shell with vendored MapLibre and Three.js.

Layer diagram
-------------

.. code-block:: text

   public sources
     -> catalog + resumable materialization
     -> normalised tree records + aligned rasters
     -> portable dataset directory (manifest.json is the contract)
     -> metrics / growth / change / DSS
     -> scene payload
     -> FastAPI + MapLibre + Three.js

Why a directory, not a database
-------------------------------

The pilot is single-user and research-oriented. JSON, GeoJSON, and NumPy archives are
reviewable, diffable, and portable. A database becomes necessary when there are
concurrent editors, roles, or per-tree work orders.

Core modules
------------

.. list-table::
   :header-rows: 1

   * - Module
     - Responsibility
   * - ``catalog``
     - YAML source registry; licence, CRS, products, access mode.
   * - ``materialize``
     - Resumable HTTP download, SHA-256, manifest.
   * - ``inventory``
     - UBC and Vancouver adapters; enrichment and imputation flags.
   * - ``terrain``
     - Raster sampling, cropping, terrain grid, cover/volume.
   * - ``lidar``
     - Point-cloud summary, DEM-cell binning, CHM from points.
   * - ``itd``
     - Local maxima plus watershed crown detection.
   * - ``change``
     - Thresholded change metrics and class grid.
   * - ``change_product``
     - Portable JSON/PNG/NPZ change product.
   * - ``allometry``
     - Species groups, height/diameter/crown models, carbon.
   * - ``calibration``
     - Local height-diameter fits from measured trees.
   * - ``metrics``
     - Composition, size, native share, Shannon, canopy metrics.
   * - ``growth``
     - Scenario edits, annual projection, cost, score.
   * - ``dss``
     - Planting candidates, comparison, exports.
   * - ``dataset``
     - Dataset writer/loader and manifest.
   * - ``scene``
     - 2D/3D payload with one local origin and image corners.
   * - ``service``
     - FastAPI routes, scenario store, assistant bridge.
   * - ``field_packet`` / ``field_analysis``
     - Field reference packet and completed-packet analysis.
   * - ``validation``
     - Detection matching, tuning, validation products.
   * - ``tiles`` / ``lidarbc`` / ``canelevation`` / ``vancouver``
     - External tile discovery and manifests.

Data contracts
--------------

- ``TreeRecord``: tree identity, WGS84 and projected coordinates, species, measured
  attributes, measured/imputed flags, source.
- ``TerrainGrid``: CRS, bounds, elevation, canopy height.
- ``Building``: footprint rings and height.
- ``DatasetManifest``: dataset id, CRS, bounds, tree count, sources, metrics, file map.
- ``ScenarioEdit``: typed append-only edit.
- ``Scenario``: base dataset, edits, horizon, revision.
- ``ScenarioResult``: metrics by year, final trees, cost, score, optional tree timeline.

Persistence
-----------

- Dataset directories are immutable inputs.
- Scenario JSON lives in ``runtime/scenarios/`` and is written atomically.
- Scenario results and tree timelines are cached in memory.
- Change products live beside the dataset as ``change*.json`` and ``change*.png``.
- Field packets and validation outputs are normal directories with CSV/GeoJSON/JSON.

Service
-------

Key route groups:

- dataset: ``/api/dataset``, ``/api/metrics``, ``/api/completeness``
- trees and scene: ``/api/trees``, ``/api/scene``, ``/api/canopy.png``,
  ``/api/hillshade.png``
- change: ``/api/changes``, ``/api/change``, ``/api/change.png``
- scenarios: ``/api/scenarios``, project, result, compare, exports
- DSS: ``/api/dss/recommend``
- assistant: ``/api/agent``, ``/api/agent/chat``

Frontend
--------

- MapLibre: local image overlays for canopy and change, GeoJSON buildings, boundary, and
  tree points.
- Three.js: heightfield terrain and instanced trunks/crowns; raycast selection.
- Shared state: one selected tree id and one scene origin for both views.
- The shell and JS/CSS are served ``no-store`` so a rebuilt raster cannot be masked by a
  stale browser cache.
- All asset and API paths are relative, so a path-prefixed reverse proxy works.

Deliberate simplifications
--------------------------

- One projected CRS per dataset; no on-the-fly raster reprojection.
- No ground classification beyond ASPRS classes; ground is excluded from canopy.
- Generic allometric growth, not a calibrated local growth model.
- No accounts, roles, work orders, or risk assessment.
- Procedural crowns, not species-specific meshes.

Extension points
----------------

- Fitted local growth model or a ``fresh-fvsbc`` adapter.
- Point-cloud segmentation or Dalponte-style region growing.
- COPC streaming for very large point clouds.
- A database-backed scenario/work-order store.
- A mobile field-entry client over the packet CSV contracts.
