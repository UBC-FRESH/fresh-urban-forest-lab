Web application guide
=====================

The application is one FastAPI process with a static browser shell. It has four working
surfaces: a 2D map, a 3D scene, observed-change products, and a scenario/analytics studio.

The shell is deliberately offline-capable. MapLibre and Three.js are vendored; the 2D
basemap is a local hillshade and canopy raster over a neutral background, not an external
tile service.

Start the app
-------------

.. code-block:: bash

   fresh-urban-forest serve \
     --dataset data/demo/ubc_core \
     --host 127.0.0.1 \
     --port 8000 \
     --allow-agent

Open ``http://127.0.0.1:8000``. The assistant is optional; ``--allow-agent`` enables the
local ``opencode`` CLI.

.. image:: /_static/demo-map.png
   :alt: 2D canopy map over the UBC core campus
   :width: 100%

Header and sidebar
------------------

- **Dataset identity**: name, tree count, source count, and live status.
- **Current canopy**: cover, trees, volume, carbon, species, native share.
- **Inventory completeness**: measured share of DBH, height, crown width, and species.
- **Scenario**: name, horizon, preview year, preview/reset, exports.
- **Tree inspector**: selected tree, measured/imputed tags, remove/replace/move.
- **Planting advisor**: species, count, budget, radius, site search, zone planting.

2D map
------

Layers:

- local hillshade
- canopy-height raster
- building footprints
- analysis boundary
- tree points coloured by species group
- selected-tree highlight
- planting candidates from the advisor

Click a tree to inspect it. Use **Plant mode** to place one tree. Use **Plant a zone** and
then click the map to centre a circular planting search; the advisor returns candidates
inside the radius.

3D scene
--------

- heightfield terrain from the dataset DEM
- instanced trunks and crowns by species group
- building extrusions with terrain-based base elevation
- orbit controls, scroll zoom, and raycast tree selection
- **Walk** mode: pointer-lock mouse look, WASD/arrow movement, Shift sprint, and
  terrain-following eye height
- shared selection state with the 2D map

The 3D scene is a context view, not a survey-grade visualization. Crown shapes are
procedural approximations.

Observed change tab
-------------------

The Change tab reads the optional change products in the dataset directory. Each product
has its own raster, metrics, and cache-busted image URL. The selector lists every
``change*.json`` file returned by ``/api/changes``.

The raster is a thresholded CHM comparison:

- loss: canopy in the earlier date, not in the later date
- stable canopy: canopy in both dates
- gain: canopy in the later date only
- no canopy: both dates below the threshold
- transparent: no valid comparison at that cell

The map fits to the valid overlap, not the whole dataset extent, and shows a faint 2021
canopy underlay for context.

.. image:: /_static/change-products.png
   :alt: Observed change tab with the full-core 2016 to 2021 product
   :width: 100%

Scenario studio
---------------

1. Add edits: remove, replace, move, plant one tree, or plant a zone.
2. Preview the scenario.
3. Scrub the **Preview year** slider from zero to the horizon.
4. Press **Play years** to animate the scenario at about 0.7 s per year.
5. Open **Analytics** to see the canopy trajectory, species composition, size classes,
   and a scenario comparison ranked by DSS score.
6. Export GeoJSON or the annual CSV.

.. image:: /_static/scenario-lab.png
   :alt: Scenario analytics, comparison, and time controls
   :width: 100%

The scenario score is a decision aid, not an objective truth. It combines canopy cover,
native share, Shannon diversity, carbon retention, and a cost penalty. The weights are in
``src/fresh_urban_forest/growth.py``.

Assistant
---------

The **+ Ask** pill opens a pop-up assistant. It sends the current view, dataset, selected
tree, scenario, metrics, and recommendation count as context. It runs the local
``opencode`` CLI with a sanitized environment. The deployment boundary is the Cloudflare
Zero Trust gateway with UBC CWL that fronts the whole dev server; the app does not add a
second login layer.

.. image:: /_static/assistant.png
   :alt: The + Ask assistant panel
   :width: 100%

See :doc:`../reference/assistant` for the endpoint contract and security notes.

Exports
-------

- ``/api/scenarios/{id}/export.geojson``: final live-tree population
- ``/api/scenarios/{id}/export.csv``: annual metric timeline
- ``/api/change``: change summary JSON
- ``/api/change.png``: change raster

All browser URLs are relative so the app works behind a path-prefixed reverse proxy such
as a code-server ``/proxy/8101/`` path.

Known UI limitations
--------------------

- No saved views, user accounts, or multi-user editing.
- Scenario edits are append-only; undo is per-edit, not a full undo stack.
- No work orders, risk forms, or photo attachments.
- The 3D scene uses procedural crowns, not species-specific meshes.
- Walk mode follows terrain and stays within the scene bounds; it does not model building
  interiors or complete physical collision. It is in-engine navigation, not Google Street
  View imagery.
- The time slider is a scenario projection, not an observed time series.
