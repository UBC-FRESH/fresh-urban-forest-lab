Street-level tree candidates
============================

Status: P63 open-data pilot; P67 full live-host sample published.

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
unique KartaView image records; the bounded run selected 1,200 images, decoded 1,167, and
produced 17,016 image components, 3,462 fused candidates, and 1,005 public-tree matches
within 8 m (median 5.20 m).

The P66 bounded sample is preserved separately as
`street_tree_candidates_sample1200.geojson` and is not the default layer.

Full live-host pass
-------------------

P67 processed every live-host KartaView image reachable through the same bounded 100-record
cell scan. It excluded 3,772 `storage1` records whose source blobs return `BlobNotFound`.
The pass selected and decoded 6,425 images across 117 populated cells, produced 96,731 tree
components and detections, and fused 19,790 candidates using a 7 m neighbour radius and a
10 m maximum component spread. Of those candidates, 11,182 are single-view, 8,608 have two
or more views, and the maximum view count is 19. The median positional uncertainty is
5.996 m and the maximum is 10.462 m.

6,078 street candidates matched a public tree record within 8 m, with a median matched
distance of 4.99 m. The layer is the current canonical street-tree layer. The 24-candidate
Commercial Drive pilot and the 85-image sparse sample are preserved as separate files.

Off-inventory is a separate LiDAR population. Of the 19,790 street candidates, 9,844 fall
within 10 m of an off-inventory candidate and 16,753 fall within 20 m; median nearest
distance is 10.05 m. That is a descriptive overlap only: the two methods see different
objects and do not establish identity.

Uncertainty audit
------------------

P68 found that none of the 6,425 selected images supplied a provider FOV value; all used
the 60° assumption. Reprojecting under 50° and 70° moved detections by a median of
1.124-1.244 m and a p95 of 2.874-3.180 m. A ±5° heading offset moved detections by a median
of 2.103 m and p95 of 4.457 m. Camera pitch remains unmodeled.

A stratified 24-detection contact sheet showed that semantic mask boxes frequently cover
canopy, sky, vehicles, facades, or signs, and that bottom-centre depth is not necessarily
the trunk. The detector is therefore a screening component detector, not a tree-instance
or trunk detector. Public-tree match counts are sensitive to tolerance: 2,008 candidates
within 4 m, 6,078 within 8 m, and 8,978 within 12 m. These are descriptive counts, not
precision estimates.

The demo layer now shows a dynamic candidate count beside the `street trees` toggle and
carries the screening caveat.

Detector and trunk-base audit
-----------------------------

P69 audited 200 stratified candidates against the existing OneFormer masks. Median tree-mask
coverage inside the box was 0.703, but 42/200 boxes had less than half tree pixels. Only
87/200 bottom-centre pixels were labelled `tree`; the rest were building, car, sky, pavement,
plant, fence, grass, or road. Multi-view candidates were somewhat better than single-view
(51/100 vs 36/100 tree at the bottom centre), but the inventory-match fraction was unchanged
at 8 m (30.3% vs 30.7%).

A Grounding DINO `tree trunk` trial (Apache-2.0) found at least one trunk detection in 20/20
sample images, but only 3/20 best trunk boxes overlapped the current candidate box; many were
margin trunks or poles. It was not integrated.

A multi-view screening subset (8,608 candidates) is available only as an external sample
file. The canonical 19,790-feature layer is unchanged. The next detector should identify a
trunk/base or use a ground-plane constraint rather than adding more imagery.

Ground-plane gate
------------------

P71 tested a level-camera check comparing ZoeDepth depth at the box bottom with the expected
ground range. It did **not** improve the P69 semantic audit. At a 2.5 m assumed camera height,
46.6% of candidates passed the gate, but only 40.6% of gate-consistent audit boxes had `tree`
at the bottom centre, versus 45.3% of gate-inconsistent boxes. A tighter ratio performed
worse. The gate is a negative result and is not integrated; camera pitch, camera height, and
bottom-surface depth remain uncalibrated.

Camera pose metadata
--------------------

P72 sampled 50 selected images and 50 KartaView sequences. Photo-level camera parameters and
pitch/roll fields were absent; all photo FOV values were zero. Only **1/50** sequences had a
nonzero sequence hFoV (67.256°); 49/50 were zero. The metadata text uses `METADATA:2.0` with
`CAMERA`, `EXIF`, `COMPASS`, and `GRAVITY` rows, but there is no documented per-photo
pitch/roll mapping. Direct metadata-driven pose calibration is therefore not available at
scale.

Details: ``notes/reports/p72-pose-audit.md``.

Details: ``notes/reports/p71-ground-gate.md``.

Details: ``notes/reports/p69-trunk-audit.md``,
``notes/reports/p69-mask-audit.json``, ``notes/reports/p69-trunk-trial.json``, and
``notes/reports/p69-confidence-sample.json``.

Details: ``notes/reports/p68-street-audit.md``,
``notes/reports/p68-fov-sensitivity.json``,
``notes/reports/p68-inventory-sensitivity.json``, and
``notes/reports/p68-detector-sample.json``.

Reproduction and full caveats are in ``notes/reports/p63-vancouver-pilot.md``,
``notes/reports/p66-citywide-street-trees.md``, and
``notes/reports/p67-full-kartaview.md``.
