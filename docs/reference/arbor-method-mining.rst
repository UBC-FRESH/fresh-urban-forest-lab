Arbor method mining and clean-room provenance
=============================================

The project uses `r-lidar/arbor <https://github.com/r-lidar/arbor>`_ as a method and
design reference for point-cloud conditioning. Arbor is a production-oriented MLS/TLS
forest point-cloud pipeline with an excellent public book. It is also **GPL-3.0**, while
this repository is MIT. We therefore mine the ideas and write independent Python code.

Source snapshot: Arbor 1.1.5, commit
``a2b487f4a23236a42eec50cb6583a5eae15593ed``, 2026-11-02. The long provenance note is
``notes/reference/arbor-method-mining.md``; the decision is ADR 0006.

What we borrowed
----------------

The first slice adds four opt-in functions in ``fresh_urban_forest.pointcloud``:

- :func:`fresh_urban_forest.pointcloud.hybrid_homogenize` — barycentric voxel decimation
  plus deterministic random reinjection, from Arbor book chapter 3.
- :func:`fresh_urban_forest.pointcloud.statistical_outlier_mask` — mean-kNN-distance
  outlier flag, from ``src/utils/sor.cpp``.
- :func:`fresh_urban_forest.pointcloud.voxel_connected_components` — sparse 6-, 18-, or
  26-connected voxel labelling, from ``src/utils/Grid3D.cpp``.
- :func:`fresh_urban_forest.pointcloud.local_anisotropy` — kNN covariance anisotropy as a
  wood-likelihood proxy, from ``src/utils/anisotopy.cpp`` and book chapter 5.
- :func:`fresh_urban_forest.pointcloud.classify_ground_ptd` — a simplified, PTD-inspired
  ALS ground classifier with TIN densification and HAG, from book chapter 4 and
  Axelsson (2000).

Each function carries a ``Method provenance`` docstring section. The note records the
source file or book chapter, the licence, and the clean-room statement.

What we did not take
--------------------

- No Arbor R or C++ source code was copied.
- No Arbor vendored C++ library was added.
- The Arbor book prose and figures were not copied; the methods are summarized in our own
  words.
- The semantic/instance pathfinder, seed detection, QSM, and QSF are not implemented here.
  They are MLS/TLS methods and belong in a future, separately tested lane.

Licence boundary
----------------

Arbor's package licence is GPL-3.0. A direct copy into this MIT repository would change
the licence of the combined work. If a future change wants to copy a specific code block
rather than reimplement it, the change stops for a licence review. The default is always a
new implementation with a named method source.

ALS ground classification
-------------------------

``classify_ground_ptd`` is a simplified, PTD-inspired implementation. It seeds a TIN from
the lowest point per grid cell, progressively adds points within a vertical residual and
TIN facet-slope threshold, and interpolates height above ground from the final surface.

It is **not** a line-by-line port of Arbor, lidR, or the original PTD code. The angle test
uses the TIN facet slope, the default vertical residual is permissive, and points outside
the TIN hull are not classified as ground. A real LidarBC tile must pass the P13.2
validation before this is used as an operational ground classifier.

What is next
------------

The next ALS step is real-tile validation: ground counts, HAG percentiles, low-point-cut
policy, and QA warnings on a small LidarBC tile. CHM/ITD post-processing (buffer flags,
small-tree flags, over-segmentation merging) is a smaller intermediate step. QSM and QSF
work belongs in a dedicated point-cloud package, not this app's core.

Citations
---------

- Roussel, J.-R. (2026). *Arbor: Tree Segmentation in MLS/TLS Point Clouds* (version
  1.1.5) [Computer software]. https://github.com/r-lidar/arbor
- Roussel, J.-R. (2026). *Arbor: The Complete R Tutorial Book*.
  https://r-lidar.github.io/arbor_book/
- Axelsson, P. (2000). DEM generation from laser scanner data using adaptive TIN models.
  *International Archives of Photogrammetry and Remote Sensing*, 33(B4/1), 110-117.
- Martin-Ducup, O., et al. (2020). Terrestrial laser scanning reveals convergence of tree
  architecture with increasingly dominant crown canopy position. *Functional Ecology*.
  https://doi.org/10.1111/1365-2435.13678
- Griese, N., Ritzert, M., & Nölke, N. (2025). A large dataset of labelled single tree
  point clouds, QSMs and tree graphs. *Scientific Data*, 12, 1953.
  https://doi.org/10.1038/s41597-025-06421-7
