# P18 CHM/ITD post-processing smoke test

Date: 2026-11-04
Phase: P18
Parent issue: #116
Task: #117
Status: smoke test complete; integration opt-in

## Dataset

`data/demo/ubc_core`, bounds E 480411-E 486201, N 5451920-N 5458722. The demo is a large
core-campus snapshot, not a small plot.

## CLI integration

`detect-trees` now accepts:

```bash
fresh-urban-forest detect-trees \
  --dataset data/demo/ubc_core \
  --out tmp/detected_post.geojson \
  --min-height 3 \
  --postprocess \
  --buffer 10 \
  --max-small-height 2
```

With `--postprocess`, the command writes kept crowns to `--out` and a sidecar summary to
`<out>.summary.json` by default. Use `--summary PATH` to override. The default command
without `--postprocess` is unchanged.

## Results

| Configuration | Detected | After merge | Kept | Buffer flags | Small flags | Merge groups |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| default (`min-height=3`, buffer 10, small 2) | 859 | 701 | 701 | 0 | 0 | 57 |
| stress (`min-height=1.5`, buffer 50, small 2) | 865 | 706 | 701 | 5 | 0 | 57 |

The default buffer of 10 m flags nothing because the demo bounds are about 5.8 km by 6.8 km
and the detector's crowns are interior. The stress run with a 50 m buffer flags 5 crowns,
which confirms the flag path. No crown is below 2 m because the detector's minimum height is
above that threshold in both runs.

The merge step reduces 859 crowns to 701 in the default run: 57 groups, 158 source crowns
merged. This is a substantial reduction. It is a CHM heuristic, not a validated instance
segmentation, so the summary must be read as a screening result.

## Summary schema

The sidecar summary is `TreePostprocessResult.to_dict()`:

- `tree_count`
- `buffer_ids`
- `small_ids`
- `merge_groups`
- `kept_ids`
- `warnings`

## Limits

- One demo dataset, not a field-validated crown map.
- The 10 m buffer flags nothing on this large interior demo; the stress run exercises it.
- The small-tree flag is not exercised because the detector minimum height is above 2 m.
- The merge reduction is large and needs visual/field review before operational use.
- The default detector output is unchanged.
