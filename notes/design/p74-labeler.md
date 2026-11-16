# P74 street-tree labeling UI and benchmark split

Parent issue: #338
Branch: `feature/p74-labeler`
Status: complete

## Goal

Provide a local labeling interface for the P73 packet and a leakage-safe benchmark split by
image ID. No model training or canonical data change.

## Approach

- Stdlib HTTP server serving only the packet manifest, crops, and label CSV.
- Browser UI for `tree_present`, `trunk_visible`, `box_quality`, and notes.
- Autosave with CSV validation and atomic writes.
- Image-grouped train/validation/test split with fixed seed.
- Local browser smoke; no external services.

## Non-goals

No labels fabricated, no model trained, no canonical/demo/tag/release change.
