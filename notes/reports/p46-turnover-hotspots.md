# P46 canopy turnover hotspots

Status: citywide turnover screen built; close-out pending.

## Method

- Input: P43 2 m citywide change grid.
- Gain = later canopy, no earlier canopy; loss = earlier canopy, no later canopy.
- 8-connected component labeling.
- Minimum patch area: **50 m²** (12.5 pixels at 4 m²).
- Patch counts, largest patch, and total turnover area aggregated to the global P38
  400 m cells.
- Cells tiered by turnover fraction across the city; joins P38–P42.

## Result

- 797 cells.
- Turnover tiers: **high 260**, medium 257, low 258, none 22.
- Gain patches: **10,430**.
- Loss patches: **7,516**.
- Total turnover area: **181.76 ha**.
- Largest gain patch: **0.596 ha**.
- Largest loss patch: **0.492 ha**.

Highest-turnover cells include `r23c34` (10.0% turnover; P44 protect-loss),
`r25c35` (9.0%; expand-canopy), and `r19c07` (8.0%; expand-canopy in the current
action join).

## Product

Under `data/processed/vancouver_2022/`:

- `canopy_turnover.json`
- `canopy_turnover.geojson`
- `canopy_turnover.png`
- `canopy_turnover_meta.json`

API: `/api/canopy-turnover` and `/api/canopy-turnover.geojson`. Map: **turnover hotspots**
toggle and sidebar summary.

## Limits

- This is a contiguous gain/loss patch screen, **not a net gain/loss claim**.
- P45 found the citywide net sign unstable across a ±1 m offset range; patch sizes are
  also sensitive to grid scale, threshold, and vertical offset.
- Temporary LiDAR artifacts, classification, and co-registration can create patches.
- No tree survival, species, ownership, causal, or field-validation claim.

## P51 controlled sidecar

P51 rebuilt P46 on the corrected P43 screen. The corrected sidecar has 259 high-tier
cells and 135.58 ha of turnover, compared with 260 cells and 181.76 ha in the original
product. These are sidecar data under `vancouver_2022_control/`, not the public API
default. Patch turnover is still a screening result, not a net-change claim. See
`notes/reports/p51-downstream-refresh.md`.
