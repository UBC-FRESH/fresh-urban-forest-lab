# P50 vertical control and P43/P45 re-evaluation

Status: complete; PR #271 open. Not merged.

## Data access

The City 2018 LiDAR index lists 181 ZIP tiles (78.04 GB). Raw tiles were not local, and an
automated request to the indexed `webtransfer.vancouver.ca` URL returned HTTP 403. A
headful browser download succeeded. A spatially distributed sample of 13 tiles was
downloaded; 878 MB on disk. Seven tiles overlapped the 2022 raster bounds and contributed
ground-control observations.

## Method

- 2018 class-2 ground points, stride 8.
- 2022 1 m DEM at the same projected coordinates, EPSG:3157.
- Exclude 2022 CHM > 1 m and building-mask pixels.
- Initial absolute difference cap: 10 m.
- Robust median with a 2 m trim; 2,000 bootstrap resamples.
- No canopy, tree, or model value used as control.
- Class-6 building roofs were not available in the sampled 2018 LAS classes; they were not
  used. Class-1 unclassified points were not used as a roof proxy.

## Control estimate

- Retained paired observations: **12,337** across seven tiles.
- Median 2018-ground minus 2022-DEM offset: **+0.008 m**.
- Median absolute deviation: **0.103 m**.
- Interquartile range: **−0.164 to +0.078 m**.
- Bootstrap 95% median interval: **+0.004 to +0.011 m**.

Per-tile medians ranged from **−0.233 m** to **+0.048 m**. The negative tile and the small
sample mean this is not a citywide probability sample.

## P43/P45 re-evaluation

P43 built the 2018 CHM using the 2022 DEM plus a **+1.0 m** vertical offset. The measured
ground-control difference is **+0.008 m**, so the correction to the P43 earlier surface is:

```text
1.0 - 0.008 = +0.992 m
bootstrap range: +0.989 to +0.996 m
```

Applying that correction to the P43 2 m change grid:

| Correction | Net | Mean height change |
| ---: | ---: | ---: |
| +0.989 m | **−94.3 ha** | +0.519 m |
| +0.992 m | **−95.4 ha** | +0.517 m |
| +0.996 m | **−97.1 ha** | +0.513 m |

The sign is negative across the measured control interval. The prior P43/P45 +1.0 m
assumption is not supported by this sample; the previous positive net result was sensitive
to that assumed offset.

## Decision

The measured control **does not support the +1.0 m P43 offset**. Under the sampled control,
the corrected screen is about **−95 ha**, not the previous **+223 ha**. However:

- the seven-tile sample is not a citywide probability sample;
- ground can be excavated, filled, or reclassified;
- classification, co-registration, scale, edge, and acquisition-season effects remain;
- class-6 roof control was unavailable;
- this is not survey-grade accuracy control or field validation.

Therefore do **not** publish a final citywide net-loss claim. The defensible statement is:

> The sampled ground control is near zero and does not support P43's assumed +1.0 m offset.
> Correcting for that control changes the screen from a positive to a slight negative net,
> but the sample is not citywide and classification/co-registration/scale effects remain.

## Products

- `data/processed/vertical_control.json` (ignored)
- `data/processed/vertical_control_sensitivity.json` (ignored)
- `scripts/estimate_vancouver_vertical_control.py`
- `scripts/analyze_vancouver_vertical_control.py`
- `fresh_urban_forest.vertical_control`
- Tests for robust offset recovery and invalid inputs

## Limits

- Not a citywide probability sample.
- Not a survey-grade vertical-accuracy assessment.
- No field validation, tree survival, ownership, causal, or planting claim.
- No final citywide gain or loss claim.
