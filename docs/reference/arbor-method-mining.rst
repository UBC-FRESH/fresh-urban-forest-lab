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
point-to-vertex angle threshold, and interpolates height above ground from the final surface.

It is **not** a line-by-line port of Arbor, lidR, or the original PTD code. The angle test
uses a point-to-triangle-vertex angle measured from the triangle plane, the default vertical
residual is permissive, and points outside the TIN hull are not classified as ground.

P13.2 validates a 415,068-point LidarBC 2025 tile (EPSG:3157, OGL-BC). Class-2 recall is
0.9998 and class-2 HAG p99 is 0.021 m. The tile's class 1 is unclassified and class 7 is
noise, so neither is a valid negative set. About 80% of class-7 near-ground noise is
labelled ground. Precision against class 2 is therefore not an accuracy estimate.

P13.3 tested SOR and a low-point policy on the 2025 tile and a 3,042,883-point 2016 tile.
SOR removes 3.98-4.09% of points, including 8.6% of class-7 noise but only 0.04-0.61% of
class-2 ground. It does not fix near-ground noise. However, 99.84% of class-7 false ground
is within 0.15 m HAG, so `low_point_mask(height_above_ground, cut_m=0.15)` is the downstream
segmentation contract. The ground labels are not noise-free.

This is not yet an operational ground classifier.

What is next
------------

P13.4 decides whether the validated preprocessing and classifier are ready for a FEMIC
adapter. A checked reference patch and a second terrain type are still required. CHM/ITD
post-processing (buffer flags, small-tree flags, over-segmentation merging) is a smaller
intermediate step. QSM and QSF work belongs in a dedicated point-cloud package, not this
app's core.

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
