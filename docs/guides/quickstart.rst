Quick start
===========

The repository ships a small, real UBC core-campus demonstration dataset, so the web
application starts without a multi-gigabyte download.

Install and run the demo
------------------------

.. code-block:: bash

   python -m venv .venv
   . .venv/bin/activate
   python -m pip install -e ".[dev,web]"
   fresh-urban-forest serve --dataset data/demo/ubc_core --port 8000 --allow-agent

Open ``http://127.0.0.1:8000``. The 2D map, the 3D scene, the scenario editor, the
planting advisor, and the optional ``+ Ask`` assistant are all served from the same
process. The assistant is off by default; ``--allow-agent`` enables the local
``opencode`` CLI. It receives the current dataset, selected tree, scenario, and metrics as
context, and can read the repository docs while answering.

.. image:: /_static/demo-map.png
   :alt: 2D canopy map over the UBC core campus
   :width: 100%

.. image:: /_static/demo-scene.png
   :alt: 3D terrain with instanced trees
   :width: 100%

Build a dataset from public sources
-----------------------------------

Download the direct sources first. The catalog records the landing page, the licence, and
the native CRS for every entry.

.. code-block:: bash

   fresh-urban-forest catalog list
   fresh-urban-forest catalog show ubc_campus_trees
   fresh-urban-forest catalog fetch --all-direct --dest data/raw

Unzip the raster archives, then build:

.. code-block:: bash

   fresh-urban-forest build \
     --ubc-trees data/raw/ubcv_campus_trees.geojson \
     --buildings data/raw/ubcv_buildings.geojson \
     --boundary data/raw/ubcv_legal_boundary.geojson \
     --dem data/raw/DEM_1m.tif \
     --chm data/raw/CHM_1m.tif \
     --out data/processed/ubc_lidar_2021 \
     --name "UBC Vancouver LiDAR 2021"

The build writes ``manifest.json``, ``trees.json``, ``metrics.json``, ``terrain.npz``,
``terrain.json``, ``buildings.geojson``, and ``boundary.geojson``. The manifest is the
contract: it records the dataset id, the CRS, the bounds, the sources, the licences, and
the baseline metrics.

Inspect and analyse
-------------------

.. code-block:: bash

   fresh-urban-forest info --dataset data/processed/ubc_lidar_2021
   fresh-urban-forest detect-trees \
     --dataset data/processed/ubc_lidar_2021 \
     --out data/processed/ubc_lidar_2021/detected_trees.geojson

External tile discovery
-----------------------

LidarBC and CanElevation expose public tile indexes. Query an AOI and write a manifest
before downloading:

.. code-block:: bash

   fresh-urban-forest tiles lidarbc \
     --bbox -123.28,49.23,-123.21,49.29 \
     --out data/raw/tiles/lidarbc_ubc.json

   fresh-urban-forest tiles index --dest data/raw/canelevation
   fresh-urban-forest tiles canelevation \
     --index data/raw/canelevation/Index_LiDARtiles_tuileslidar.gpkg \
     --bbox -123.28,49.23,-123.21,49.29 \
     --provider BC \
     --out data/raw/tiles/canelevation_ubc.json

   fresh-urban-forest tiles fetch \
     --manifest data/raw/tiles/lidarbc_ubc.json \
     --dest data/raw/tiles

The manifests record the query bbox, acquisition year, projection, density, source URL,
and metadata URL. The CanElevation tile index is large (about 428 MB), so the helper reads
it with a bounding-box filter.

Observed change
---------------

Build a change product from two datasets and open the **Change** tab:

.. code-block:: bash

   fresh-urban-forest build-change \
     --earlier data/processed/ubc_lidar_2016 \
     --later data/processed/ubc_lidar_2021 \
     --out-dir data/processed/change_2016_2021

The product writes ``change.json``, ``change.png``, and ``change_grid.npz``. The service
exposes them at ``/api/change`` and ``/api/change.png``. The product compares only cells
valid in both dates and reports the overlap area; outside that overlap it is transparent.

Repeat measures
---------------

.. code-block:: bash

   fresh-urban-forest change \
     --earlier data/processed/ubc_lidar_2015 \
     --later data/processed/ubc_lidar_2021 \
     --out data/processed/canopy_change_2015_2021.json

The result reports gain, loss, stable canopy, net change, and mean height change on
stable canopy. It is a thresholded area comparison, not a growth estimate. Read
:doc:`../reference/methods` before interpreting it.

Where the data comes from
-------------------------

:doc:`data` lists the UBC, City of Vancouver, and Metro Vancouver sources, their
licences, and the traps that matter for change analysis.
