# P46 canopy turnover hotspots

Parent issue: #231
Branch: `feature/p46-turnover-hotspots`
Status: planned

## Goal

Use the P43 2 m change grid to identify contiguous gain and loss patches and summarize
turnover concentration on the 400 m P38 grid.

P45 showed the citywide net direction is not resolved. This phase therefore avoids net
gain/loss claims and reports observed turnover patches only.

## Method

- Loss = earlier canopy and no later canopy; gain = later canopy and no earlier canopy.
- Label 8-connected patches on the 2 m grid.
- Drop patches below a documented minimum area (start with 50 m²).
- Aggregate patch counts, largest patch area, and total turnover area to 400 m cells.
- Join P38 shade/equity, P39 gaps, P40 heat equity, and P42 actions.
- Tier cells by turnover area relative to the city distribution.

## Acceptance

- Minimum patch area and connectivity are documented.
- Cells report gain/loss patch counts, largest patches, and turnover area.
- Net gain/loss is not claimed.
- API, GeoJSON, map toggle, and method note are optional and documented.
- Dashboard green.
