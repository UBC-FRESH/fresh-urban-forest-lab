# P32.3 detection-refinement experiments

Date: 2026-11-06

Status: experiment only. The baseline detector remains the production screening detector.
No app layer was changed.

## Variable-window experiments

The baseline is a 2 m block-max CHM, 5 m local-maxima window, watershed, and centroid
location: 528,812 crowns and 76.6% held-out public-tree recall at 5 m.

I tested three alternatives with the same fixed 1,000-tree sample:

| Variant | Window rule | Crowns | Recall |
| --- | --- | ---: | ---: |
| Baseline | 5 m | 528,812 | 76.6% |
| variable-1 | 3 m below 8 m; 7 m 8–18 m; 11 m above 18 m | 413,981 | 63.8% |
| variable-2 | 1 m below 8 m; 3 m 8–18 m; 5 m above 18 m | 696,362 | 71.3% |
| peak-location | baseline windows, local-maximum location instead of segment centroid | 527,824 | 71.3% |

All variants reduced public-tree recall. The larger windows merge adjacent crowns; the
smaller windows over-segment; moving the reported point to the peak makes the 5 m matching
worse for segment-shaped crowns. None is adopted.

## Point-support pilot

I sampled 30 of the 300 labelled audit candidates (10 per confidence band) and read their
2022 LAS tiles in 2 m chunks. Vegetation classes were 3/4/5; support was the count inside
the candidate crown radius.

| Label | n | Median vegetation points | Mean |
| --- | ---: | ---: | ---: |
| Tree | 20 | 3,913 | 7,084 |
| Non-tree | 6 | 444 | 1,048 |
| Uncertain | 4 | 1,209 | 1,239 |

A 500-point support floor retained 19/20 tree labels and 3/6 non-tree labels in this small
pilot; a 1,000-point floor retained 18/20 tree and 2/6 non-tree. The pilot suggests real
separation, but the sample is too small and too unbalanced to choose a threshold.

## Next

Build point support for all 336,350 candidates from the 181 raw tiles, using a per-tile
1 m vegetation-point count raster and crown-radius sums. Then choose thresholds only on the
fixed validation samples, not on the full candidate set.

The production candidate layer and app are unchanged.
