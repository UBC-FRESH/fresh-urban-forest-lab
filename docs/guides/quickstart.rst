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
   fresh-urban-forest serve --dataset data/demo/ubc_core --port 8000

Open ``http://127.0.0.1:8000``. The 2D map, the 3D scene, the scenario editor, and the
planting advisor are all served from the same process.

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
