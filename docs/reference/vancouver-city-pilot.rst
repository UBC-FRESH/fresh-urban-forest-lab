Vancouver full-city pilot
=========================

The Vancouver pilot applies the lab to the full City of Vancouver using only public,
downloadable data. It is the first city-scale test of the same canopy, carbon, and 3D
stack that the UBC demo uses.

Status: active P16 work. The plan of record is
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
SHA-256 hashes are in ``notes/reports/p16-source-lock.json``. The working storage budget
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

Limits
------

- A single leaf-on LiDAR snapshot cannot support annual growth or phenology claims.
- Public trees exclude private trees; LiDAR includes private canopy but not species.
- Carbon and sequestration use generic allometry; no local destructive or repeat-measure
  calibration exists.
- Rainfall interception is a screening range, not a measured flux.
- The 3D scene is a visual sample, not a survey model.
- The City 2022 product covers the city and UBC Endowment Lands, not the whole region.
