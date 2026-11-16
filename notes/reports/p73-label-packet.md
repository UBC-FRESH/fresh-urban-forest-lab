# P73 street-tree detector labeling packet

Status: implementation complete; PR #337 open for approval.

## Packet

- **400** candidates: 100 per stratum
  - single-view matched
  - single-view unmatched
  - multi-view matched
  - multi-view unmatched
- **400** 512×512 crops with the current box overlay.
- Blank CSV labels and a JSON manifest.
- One contact sheet per stratum.

Packet location:

`/srv/shared-data/gep/ws4/external/street_trees/p73_label_packet`

Files:

- `crops/` — 400 labeled crop candidates
- `labels.csv` — blank label sheet
- `sheets/` — four contact sheets
- `notes/reports/p73-label-manifest.json`

## Label schema

| Field | Values |
| --- | --- |
| `tree_present` | yes / partial / no |
| `trunk_visible` | yes / no |
| `box_quality` | good / loose / bad |
| `notes` | free text |

## Why this exists

P69 found that bottom-centre depth often lands on buildings, cars, sky, or facades. P71 and
P72 could not solve this with ground-plane heuristics or available pose metadata. A trained
detector needs explicit labels; this packet is the required input, not a detector.

## Limits

- Labels are blank; no human labels have been collected.
- No model was trained.
- No canonical, demo, tag, or release change.
