# P73 street-tree detector labeling packet

Parent issue: #336
Branch: `feature/p73-label-packet`
Status: pr-open

## Goal

Create a reproducible human-labeling packet for a future trained tree/trunk detector.

## Approach

- Select 100 candidates per stratum: single/multi-view × matched/unmatched.
- Export 512×512 crops with the current box overlaid.
- Export a blank CSV label schema and machine-readable manifest.
- Render one contact sheet per stratum.
- Keep the canonical layer and demo unchanged.

## Labels

- `tree_present`: yes / partial / no
- `trunk_visible`: yes / no
- `box_quality`: good / loose / bad
- `notes`: free text

## Non-goals

No model training, field validation, precision/recall, ownership, survival, or canonical data
change.
