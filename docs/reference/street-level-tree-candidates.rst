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

Layer and API
-------------

The Vancouver pilot is published as a selectable map layer when the dataset contains
``street_tree_candidates.geojson``. The dataset advertises ``has_street_trees``; the layer
toggle is hidden when that flag is false.

- ``GET /api/street-trees`` returns the method, counts, provenance, and caveats.
- ``GET /api/street-trees.geojson`` returns the candidate FeatureCollection.

The map source is independent of the off-inventory source. Clicking a street candidate
opens a screening-point popup; it does not select an official tree or an off-inventory
candidate.

Pilot
-----

The first Vancouver pilot used eight KartaView images around the Commercial Drive area. It
produced 24 fused candidates from 111 image components; six candidates matched a public
tree within 8 m, with a median matched distance of 5.35 m. This is a screening result, not a
detection rate: the public inventory does not contain all private trees.

Limits
------

- Assumed FOV and uncalibrated camera pitch.
- Semantic masks plus distance-peak splitting are not a trained tree-instance detector.
- Imagery is from 2016; inventory records are current.
- No field validation, private-tree census, ownership, survival, or citywide claim.
- The current layer does not replace or modify the LiDAR off-inventory population.

Citywide sample
---------------

P66 extended the pilot to a 118-cell, 1 km boundary grid. The metadata audit found 10,204
unique KartaView image records; the bounded run selected 500 images, decoded 85, and
produced 1,023 image components, 258 fused candidates, and 70 public-tree matches within
8 m (median 5.32 m).

The citywide layer is the current canonical street-tree layer. The 24-candidate Commercial
Drive pilot is preserved as `street_tree_candidates_commercial_pilot.geojson` and is not
served as the default layer.

Off-inventory is a separate LiDAR population. Of the 258 street candidates, 106 fall within
10 m of an off-inventory candidate. That is a descriptive overlap only: the two methods see
different objects and do not establish identity.

Reproduction and full caveats are in ``notes/reports/p63-vancouver-pilot.md`` and the P66
coverage summary.
