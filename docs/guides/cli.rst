Command-line guide
==================

The CLI is the reproducible path. Every web feature is backed by a command, a dataset
file, or an API endpoint that can be called without the browser.

Entry point
-----------

.. code-block:: bash

   fresh-urban-forest --help

The package also runs as ``python -m fresh_urban_forest.cli``.

Catalog and sources
-------------------

.. code-block:: bash

   fresh-urban-forest catalog list
   fresh-urban-forest catalog search lidar
   fresh-urban-forest catalog show ubc_campus_trees
   fresh-urban-forest catalog fetch --all-direct --dest data/raw

Catalog entries record the publisher, licence, native CRS, products, and whether the URL
is a direct download or a landing page. A catalog-only source is skipped by
``catalog fetch`` and recorded as a failed materialization with a clear message.

Build a dataset
---------------

.. code-block:: bash

   fresh-urban-forest build \
     --ubc-trees data/raw/ubcv_campus_trees.geojson \
     --buildings data/raw/ubcv_buildings.geojson \
     --boundary data/raw/ubcv_legal_boundary.geojson \
     --dem data/raw/DEM_1m.tif \
     --chm data/raw/CHM_1m.tif \
     --out data/processed/ubc_lidar_2021 \
     --name "UBC Vancouver LiDAR 2021"

Optional:

- ``--vancouver-trees PATH`` adds the City public-tree CSV.
- ``--dsm PATH`` derives a CHM when ``--chm`` is absent.
- ``--laz PATH`` prints a point-cloud summary.
- ``--bbox min_lon,min_lat,max_lon,max_lat`` filters the inventory.
- ``--max-trees N`` samples the inventory.

The writer produces ``manifest.json``, ``trees.json``, ``metrics.json``,
``terrain.npz``, ``terrain.json``, ``buildings.geojson``, and ``boundary.geojson``.

Inspect and detect
------------------

.. code-block:: bash

   fresh-urban-forest info --dataset data/demo/ubc_core

   fresh-urban-forest detect-trees \
     --dataset data/demo/ubc_core \
     --out data/demo/ubc_core/detected_trees.geojson

``detect-trees`` uses local maxima plus marker-controlled watershed on the dataset canopy
grid. Add ``--postprocess`` to apply the opt-in edge buffer, small-tree flag, and
conservative over-segmentation merge. The command writes kept crowns to ``--out`` and a
sidecar summary to ``<out>.summary.json`` unless ``--summary`` is supplied.

.. code-block:: bash

   fresh-urban-forest detect-trees \
     --dataset data/demo/ubc_core \
     --out tmp/detected_post.geojson \
     --min-height 3 \
     --postprocess \
     --buffer 10 \
     --max-small-height 2

Without ``--postprocess`` the command and output are unchanged.

Tile discovery
--------------

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

   fresh-urban-forest tiles vancouver \
     --year 2022 \
     --bbox -123.28,49.23,-123.21,49.29 \
     --out data/raw/tiles/vancouver_2022_ubc.json

   fresh-urban-forest tiles fetch \
     --manifest data/raw/tiles/lidarbc_ubc.json \
     --dest data/raw/tiles

``tiles fetch`` is resumable and writes a materialization record per tile. For a publisher
that blocks automated clients with a browser challenge, use the operator helper:

.. code-block:: bash

   xvfb-run -a python scripts/browser_download_tiles.py \
     --manifest data/raw/tiles/vancouver_2022_ubc.json \
     --dest data/raw/city_lidar/2022

Change products
---------------

Build a product from two dataset directories:

.. code-block:: bash

   fresh-urban-forest build-change \
     --earlier data/processed/ubc_lidar_2016 \
     --later data/processed/ubc_lidar_2021 \
     --out-dir data/processed/change_2016_2021

Write only the JSON summary with the older command:

.. code-block:: bash

   fresh-urban-forest change \
     --earlier data/processed/ubc_lidar_2015 \
     --later data/processed/ubc_lidar_2021 \
     --out data/processed/canopy_change_2015_2021.json

Detection validation and tuning
-------------------------------

.. code-block:: bash

   fresh-urban-forest validate-detection \
     --dataset data/processed/ubc_lidar_2021 \
     --chm data/raw/ubc/lidar_2021/CHM_1m.tif \
     --bbox -123.255,49.255,-123.240,49.268 \
     --min-height 3 \
     --window 6 \
     --out-dir data/processed/validation_2021_core

   fresh-urban-forest tune-detection \
     --dataset data/processed/ubc_lidar_2021 \
     --chm data/raw/ubc/lidar_2021/CHM_1m.tif \
     --bbox -123.255,49.258,-123.245,49.265 \
     --min-heights 3,4,5 \
     --windows 3,4,5,6,8,10 \
     --out data/processed/tuning_2021_mainmall.json

Field packet
------------

.. code-block:: bash

   fresh-urban-forest field-packet \
     --dataset data/processed/ubc_lidar_2021 \
     --chm data/raw/ubc/lidar_2021/CHM_1m.tif \
     --bbox -123.255,49.258,-123.245,49.265 \
     --min-height 3 \
     --window 6 \
     --max-trees 200 \
     --out-dir data/processed/field_packet_mainmall

After field work:

.. code-block:: bash

   fresh-urban-forest analyze-field-packet \
     --packet data/processed/field_packet_mainmall \
     --out-dir data/processed/field_packet_mainmall/analysis

Allometry
---------

.. code-block:: bash

   fresh-urban-forest fit-allometry \
     --dataset data/processed/ubc_lidar_2021 \
     --out data/processed/allometry_ubc.json

This fits a height-diameter curve by species group from measured trees. It is not an
annual growth calibration.

Serve the app
-------------

.. code-block:: bash

   fresh-urban-forest serve \
     --dataset data/demo/ubc_core \
     --host 127.0.0.1 \
     --port 8000 \
     --allow-agent

The default bind is loopback. A non-loopback bind requires ``--allow-remote``.

Common failure messages
-----------------------

- **catalog-only source**: open the landing page and choose a release; the catalog is not a
  download URL.
- **DEM and CHM must share the same grid**: the builder trims edge differences, but a
  larger mismatch means the products are from different tiles.
- **opencode is not on the service PATH**: the assistant is enabled but the executable is
  unavailable.
- **this dataset has no change product**: run ``build-change`` or copy a ``change*.json``
  and its PNG into the dataset directory.
