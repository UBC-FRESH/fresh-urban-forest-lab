Vancouver full-city pilot
=========================

The Vancouver pilot applies the lab to the full City of Vancouver using only public,
downloadable data. It is the first city-scale test of the same canopy, carbon, and 3D
stack that the UBC demo uses.

Status: active P30 work. The plan of record is
``notes/design/vancouver-city-pilot.md``; the task state is in ``ROADMAP.md``.

Data
----

.. list-table::
   :header-rows: 1

   * - Source
     - Coverage and products
     - Licence
   * - City of Vancouver LiDAR 2022
     - 181 classified tiles, about 49 points/m², EPSG:3157, CGVD28GVRD; LAS
     - Open Government Licence – Vancouver
   * - City of Vancouver public trees
     - 184,152 public-tree records; species, DBH, height, local area
     - Open Government Licence – Vancouver
   * - City of Vancouver local-area boundary
     - 22 polygons; union area 118.76 km²
     - Open Government Licence – Vancouver
   * - City of Vancouver building footprints 2015
     - 154,124 approximate footprints for masks and 3D context
     - Open Government Licence – Vancouver
   * - Environment Canada climate normals
     - Vancouver Harbour CS, 1981–2010, 1,098.8 mm/yr
     - Open Government Licence – Canada

The full raw and processed products stay outside git. Source counts, byte sizes, and
SHA-256 hashes are in ``notes/reports/p30-source-lock.json``. The working storage budget
is 250 GB on ``/srv/shared-data``.

Processing
----------

1. The 22 local-area polygons are reprojected to EPSG:3157 and unioned into the AOI.
2. Each City LAS tile is rasterised to a 1 m DEM, DSM, vegetation surface, building
   surface, and water mask. The LAS uses the ASPRS class scheme: 3 low vegetation, 4
   medium vegetation, 5 high vegetation, 6 building, 9 water. The City portal's class
   wording is not used.
3. The CHM is ``max(0, max(class 3,4,5) - DEM)``.
4. Tiles are mosaicked on a 1 m grid and clipped to the AOI.
5. The full public-tree inventory is enriched with CHM height and measured/imputed flags.
6. City and local-area metrics are calculated from the CHM and the inventory.

Metrics
-------

- canopy cover: CHM at least 2 m, excluding buildings and water;
- canopy volume: summed CHM height times cell area;
- carbon storage: Jenkins et al. (2003) allometry from DBH and species group;
- annual sequestration: one-year growth projection difference;
- rainfall interception: canopy area times 1,098.8 mm/yr times a 10–20% screening range;
- species diversity and native share from the public inventory;
- tree and canopy height distributions.

Every metric names its method and evidence tier in ``city_metrics.json``. Carbon,
sequestration, and rainfall are modelled or screening estimates, not contractor-grade
audits.

Results
-------

The first full build produced:

- 181 tiles, 8,721,285,369 points, 118.77 km² AOI, 99.96% LiDAR coverage;
- 184,151 mapped public trees from 184,152 source rows;
- canopy cover 26.9%;
- height-field canopy volume 350.2 million m³;
- above-ground carbon storage about 95,800 t;
- annual sequestration about 1,980 t/yr from the one-year growth model;
- rainfall interception potential 3.50–7.01 million m³/yr at a 10–20% range;
- inventory-to-LiDAR height bias -0.397 m and RMSE 4.292 m over 162,497 pairs;
- tree shade 29.3% and combined building-plus-tree shade 43.1% on the representative
  June/September samples.

The City's 2025 Urban Forest Strategy reports about 25% canopy cover for 2022. The pilot's
26.9% is a sanity check, not a calibration: the City mask, threshold, and land base differ.
Local-area cover ranges from 47.5% in Shaughnessy to 9.6% in Strathcona; the app shows
all 22 local areas.

Web app
-------

Build the city pack and serve it:

.. code-block:: bash

   python scripts/build_vancouver_city.py --jobs 8
   python scripts/build_vancouver_inventory.py
   python scripts/build_vancouver_metrics.py
   python scripts/build_vancouver_pack.py
   fresh-urban-forest serve --dataset data/processed/vancouver_2022 --port 8000

The app exposes the city tab at ``/api/city-metrics``. The 2D map, 3D scene, tree
inspector, Light tab, and analytics use the same city dataset. The 3D scene uses a
representative visual tree sample; metrics always use the full inventory.

The 2D map loads all 184,151 public-tree points and all 154,124 building footprints from
compressed GeoJSON after the app is live. The 3D scene loads all 184,151 trees and all
154,123 building footprints as axis-aligned building massing boxes; metrics always use the
full inventory. Road centrelines are loaded from OpenStreetMap for a pale 2D underlay and a
3D street overlay. The `streets` toggle controls both.

Demo portal
-----------

The UBC and Vancouver demos share one landing page on the existing FRESH Urban Forest Lab
dev-server port, ``8101``. The WS4 portal stays on ``8790``.

.. code-block:: bash

   ./scripts/run_portal.sh

Then open ``http://127.0.0.1:8101/``. The UBC app is at ``/ubc/`` and the Vancouver app is
at ``/vancouver/``. Behind the lab proxy the paths are
``/proxy/8101/``, ``/proxy/8101/ubc/``, and ``/proxy/8101/vancouver/``.

.. image:: /_static/vancouver-city-portal.png
   :alt: Landing page with UBC campus and Vancouver city demo cards
   :width: 100%

.. image:: /_static/vancouver-city-metrics.png
   :alt: Vancouver city metrics tab with canopy cover, volume, carbon, sequestration, rainfall, and local-area ranking
   :width: 100%

.. image:: /_static/vancouver-city-3d.png
   :alt: Vancouver city 3D canopy, buildings, and terrain at city scale
   :width: 100%

.. image:: /_static/vancouver-city-map.png
   :alt: Vancouver 2D canopy map with the city boundary and 47k visual tree points
   :width: 100%

Limits
------

- A single leaf-on LiDAR snapshot cannot support annual growth or phenology claims.
- Public trees exclude private trees; LiDAR includes private canopy but not species.
- Carbon and sequestration use generic allometry; no local destructive or repeat-measure
  calibration exists.
- Rainfall interception is a screening range, not a measured flux.
- The 3D scene is a visual sample, not a survey model.
- The City 2022 product covers the city and UBC Endowment Lands, not the whole region.
