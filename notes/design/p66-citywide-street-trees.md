# P66 citywide street-level tree candidates

Parent issue: #322
Branch: `feature/p66-citywide-street-trees`
Status: pr-open

## Goal

Extend the Commercial Drive street-level pilot to a citywide Vancouver screening sample
using KartaView imagery and the existing P63/P64 pipeline.

## Approach

- Build a 1 km grid over the Vancouver dataset bounds and retain cells inside the boundary.
- Query KartaView within a 600 m radius of each grid centre, deduplicating image IDs.
- Select a bounded number of images per cell to spread coverage rather than favouring one
  corridor.
- Download available images, skipping CDN failures.
- Run OneFormer tree masks, distance-peak splitting, and ZoeDepth metric depth.
- Fuse detections with a 7 m radius.
- Compare candidates descriptively to the public inventory.
- Preserve the Commercial Drive pilot as a separate historical layer.
- Publish a new citywide screening layer and coverage summary.

## Limits

- KartaView is crowd-sourced and does not cover every street period.
- FOV remains assumed at 60° unless provider metadata exists.
- Imagery dates are mixed; inventory is current.
- Single-view candidates dominate in sparse coverage.
- No precision, recall, survival, ownership, or field-validation claim.
- No merge with LiDAR off-inventory or official inventory.

## Tasks

- [ ] P66.1 Road/grid sampling and image coverage audit
- [ ] P66.2 Citywide inference, fusion, and canonical layer
- [ ] P66.3 Validation, docs, PR, and close-out
