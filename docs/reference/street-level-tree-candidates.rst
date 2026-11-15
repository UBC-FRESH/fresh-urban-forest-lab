Street-level tree candidates
============================

Status: P63 open-data pilot.

This layer maps tree candidates visible in street-level imagery. It complements, but does
not replace, the official tree inventory or the LiDAR-derived
:doc:`off-inventory-canopy` layer.

Method
------

The pilot follows the idea of Lumnitz et al. (2021): detect tree instances in street-level
images, estimate a camera-to-tree distance, project each detection into map coordinates,
and fuse observations from multiple viewpoints. It uses an open semantic segmenter and a
metric monocular-depth model rather than the original Mask R-CNN weights.

- Imagery: KartaView public API, CC BY-SA 4.0.
- Segmentation: OneFormer ADE20K, MIT.
- Depth: ZoeDepth NYU/KITTI, MIT.
- Inventory match: City of Vancouver public-tree records, OGL-Vancouver.

KartaView often omits horizontal field of view. The pilot records an assumed **60°** FOV;
that assumption is a positional-error source, not a measured camera calibration.

Candidate contract
------------------

Street candidates are emitted separately from LiDAR candidates:

- ``source`` is ``street_level_cv``;
- ``not_ground_truth`` is ``true``;
- ``view_count`` and ``positional_uncertainty_m`` are explicit;
- the source imagery licence and attribution are recorded with the run;
- candidates are never merged into ``off_inventory.geojson`` or the official inventory.

Pilot
-----

The first Vancouver pilot used eight KartaView images around the Commercial Drive area. It
produced 29 fused candidates from 75 image components; six candidates matched a public tree
within 8 m, with a median matched distance of 5.41 m. This is a screening result, not a
detection rate: the public inventory does not contain all private trees.

Limits
------

- Assumed FOV and uncalibrated camera pitch.
- Semantic masks plus watershed splitting are not a trained tree-instance detector.
- Imagery is from 2016; inventory records are current.
- No field validation, private-tree census, ownership, survival, or citywide claim.
- The current layer does not replace or modify the LiDAR off-inventory population.

Reproduction and full caveats are in ``notes/reports/p63-vancouver-pilot.md``.
