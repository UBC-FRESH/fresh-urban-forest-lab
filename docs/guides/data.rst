Public data
===========

The pilot uses public sources with clear licences. The repository does not redistribute
the full LiDAR products. It ships a small derived demo and records the source lineage in
``data/demo/ubc_core/manifest.json``.

UBC
---

- **Campus tree inventory** (``UBCGeodata/ubc-geospatial-opendata``): about 9,300 points,
  PDDL-1.0. Many records are location-only; about half have height, DBH, and crown width.
- **2021 LiDAR** (Abacus ``hdl:11272.1/AB2/Y5KQNB``): LAZ tiles plus 1 m CHM, DEM, and
  DSM. Acquired 2021-06-23. EPSG:3157.
- **Earlier LiDAR**: 2005 (shoreline), 2010 (cliffs/bare earth), 2015 (campus).
- **Buildings and legal boundary**: PDDL-1.0, useful for context and planting constraints.

City of Vancouver
-----------------

- **Public trees**: daily CSV export under the Open Government Licence – Vancouver.
  Includes public boulevard and park trees, not private trees.
- **LiDAR 2013, 2018, 2022**: three citywide repeat acquisitions at about 12, 30, and 49
  points/m². The 2013 flight is winter; 2018 and 2022 are late summer. A raw difference
  confounds phenology and acquisition conditions with real change.

Metro Vancouver
---------------

- **Classified LiDAR 2022**: about 16.5 GB for Vancouver, UBC, UEL, and Electoral Area A.
  It is the strongest independent cross-check because vegetation is classified.

See ``notes/reference/data-sources.md`` for the full table, field lists, coordinate
systems, and caveats. See ``DATA_LICENSES.md`` for attribution.
