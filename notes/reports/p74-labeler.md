# P74 street-tree labeling UI and benchmark split

Status: complete. Squash-merged in PR #339 as `c1c9498`.

## Labeling UI

Local-only stdlib server:

```bash
PYTHONPATH=src:scripts python scripts/street_tree_labeler.py \
  --packet-dir /srv/shared-data/gep/ws4/external/street_trees/p73_label_packet \
  --manifest notes/reports/p73-label-manifest.json \
  --labels /srv/shared-data/gep/ws4/external/street_trees/p73_label_packet/labels.csv
```

Open `http://127.0.0.1:8123/`.

Features:

- 400 crops from the P73 packet.
- `tree_present`: yes / partial / no.
- `trunk_visible`: yes / no.
- `box_quality`: good / loose / bad.
- notes field.
- keyboard shortcuts and previous/next navigation.
- autosave to the CSV with atomic writes and validation.
- no external calls.

Browser smoke with a temporary labels file:

- page loaded, 400 samples;
- labels changed and saved;
- CSV row written with the expected fields;
- no console or page errors.

## Benchmark split

Image-grouped split, seed 74:

| Split | Images | Candidates |
| --- | ---: | ---: |
| train | 277 | 279 |
| validation | 60 | 60 |
| test | 60 | 61 |

The split is by `image_id`, so crops from one source image cannot leak across splits. It
contains no labels.

Files:

- `notes/reports/p74-benchmark-split.json`
- `/srv/shared-data/gep/ws4/external/street_trees/p73_label_packet/benchmark_split.json`

## Limits

- Labels are still blank in the packet CSV.
- No model was trained.
- No canonical, demo, tag, or release change.
