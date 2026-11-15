# P68 street-layer UI cue and calibration audit

Status: implementation complete; PR pending approval.

## Demo UI cue

The Vancouver demo now shows a dynamic count beside the `street trees` checkbox:

> street trees · 19,790

The count comes from `/vancouver/api/street-trees`, so it changes with the dataset. The
label carries the caveat: "Screening candidates from street-level imagery; not confirmed
trees or official inventory." The badge stays hidden when the dataset has no street-tree
layer.

Browser verification on a P68 dev server:

- toggle visible, enabled, and checkable;
- count rendered as **19,790**;
- no console or page errors.

## FOV metadata

- 6,425 selected images; **0** had a provider horizontal-FOV value.
- All 6,425 used the assumed **60°** horizontal FOV.
- Provider image dimensions disagreed with the decoded image for **6,394** of 6,425 images.
  The audit uses decoded dimensions; the production run already did the same.
- 1,017 detections (68 image IDs) lacked current metadata after the provider query changed;
  those detections retain their baseline position. This is **1.05%** of detections.

## FOV sensitivity

Cached detections were reprojected and re-fused under 50°, 60°, and 70° horizontal FOV.
The 60° case reproduces the baseline exactly: 19,790 candidates and 6,078 inventory matches.

| Assumed FOV | Candidates | Inventory matches ≤8 m | Median displacement | p95 displacement | Baseline candidates within 5 m |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 50° | 18,782 | 5,822 | 1.124 m | 2.874 m | 18,501 / 19,790 (93.5%) |
| 60° | 19,790 | 6,078 | 0.000 m | 0.000 m | 19,790 / 19,790 |
| 70° | 20,719 | 6,225 | 1.244 m | 3.180 m | 18,933 / 19,790 (95.7%) |

Within 10 m, 19,786 of 19,790 baseline candidates have a 50° candidate and all 19,790 have
a 70° candidate. FOV uncertainty changes candidate counts and matched counts, but the
median matched distance remains near 5.0 m.

## Heading and depth

- Heading offsets of ±5° move detections by a median of **2.103 m** and p95 of **4.457 m**.
- At ±5°, 18,062/19,790 and 18,050/19,790 baseline candidates remain within 5 m.
- Camera pitch is not modeled; the projection assumes a level pinhole camera.
- ZoeDepth depth has median **22.947 m**, p95 **50.099 m**, and maximum **80.176 m**.

The heading and depth results are more consequential than the ±10° FOV range. The detector
boxes and depth at the box-bottom-centre are the main positional weakness.

## Detector sample

A stratified convenience sample of 24 detections was rendered with source boxes:

- 8 single-view candidates with a public tree within 8 m;
- 8 single-view candidates without a public tree within 8 m;
- 8 candidates with three or more views.

Contact sheet (operator artifact, not committed):

`/srv/shared-data/gep/ws4/external/street_trees/p68_detector_contact_sheet.png`

Sample manifest: `notes/reports/p68-detector-sample.json`.

Observations:

- Several boxes cover canopy, sky, vehicles, facades, or signs rather than a distinct tree
  base.
- Some boxes cover a useful tree crown but the bottom-centre depth point is not the trunk.
- Large canopy boxes can produce 20-50 m depths, consistent with the depth distribution.
- The detector is a semantic mask plus component splitting, not an instance or trunk
  detector. This sample is not an accuracy estimate and must not be used as a precision
  claim.

## Inventory tolerance sensitivity

Public-tree matching remains descriptive because the inventory is incomplete for private
trees.

| Tolerance | P67 full matches | Fraction | P66 1,167-image sample |
| ---: | ---: | ---: | ---: |
| 4 m | 2,008 | 10.2% | 312 / 3,462 (9.0%) |
| 6 m | 4,089 | 20.7% | 647 / 3,462 (18.7%) |
| 8 m | 6,078 | 30.7% | 1,005 / 3,462 (29.0%) |
| 10 m | 7,681 | 38.8% | 1,275 / 3,462 (36.8%) |
| 12 m | 8,978 | 45.4% | 1,496 / 3,462 (43.2%) |

The full layer's median nearest public-tree distance is 13.47 m; p95 is 60.52 m. The 8 m
tolerance is useful for descriptive comparison, not a validated match threshold.

## Release decision

No tag or release is created. The P67 data layer remains live; P67 and P68 PRs remain
separate approval gates. The next technical step should be a trunk/instance detector or a
calibrated pose model, not more KartaView volume.

## Limits

- No field validation, precision/recall, ownership, survival, or complete-census claim.
- FOV, heading, pitch, and depth are uncalibrated.
- The detector sample is a convenience sample, not a random accuracy audit.
- Street candidates remain separate from LiDAR off-inventory and official inventory.
