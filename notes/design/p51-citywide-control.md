# P51 citywide vertical-control sample and corrected change products

Parent issue: #272
Planned branch: `feature/p51-citywide-control`
Status: complete

## Why

P50 showed that the P43 **+1.0 m** offset is not supported by a seven-tile ground-control
sample. The measured offset is **+0.008 m**, which changes the 2 m screen from about
**+223 ha** to about **−95 ha**.

Seven tiles are not a citywide sample. P51 expands the control sample, tests whether a
stable correction can be defended, and only then produces versioned corrected products.

## Scope

- Select 30–50 spatially distributed 2018 tiles with a deterministic rule.
- Download via the headful browser path when automated requests are blocked.
- Record tile ids, checksums, bounds, sizes, and sample coverage.
- Reuse class-2 ground versus 2022 DEM control; no canopy control.
- Estimate per-tile offsets, spatial variation, and either a constant or per-tile correction.
- Produce a **versioned corrected P43 screen**; never overwrite the released P43 product.
- Refresh P44/P46 only if the control result is stable.
- Update APIs/docs only where supported; retain explicit non-final language.

## Out of scope

- Field validation or survey-grade accuracy claims.
- A final citywide net-loss/gain claim if the sample is not representative.
- Tree survival, ownership, planting, or causal claims.
- New scenario UI or unrelated product work.

## Sample design

- Use the City 2018 tile index and a 6 × 6 spatial bin grid over the city bounds.
- Select one tile per populated bin, preferring the smallest complete ZIP, plus the seven
  P50 tiles if not already selected.
- Target 36 tiles; allow 30–50 after deduplication.
- Record the exact selection, source URL, SHA-256, bbox, size, and local path.
- Keep the sample fixed for reproducibility; do not silently replace tiles.

## Control estimate

For each tile:

- class-2 ground points, stride 8;
- 2022 DEM at the same projected coordinates;
- exclude 2022 CHM > 1 m and building-mask pixels;
- initial |difference| ≤ 10 m;
- robust median and MAD.

For the sample:

- per-tile medians and counts;
- weighted and unweighted medians;
- bootstrap 95% interval;
- spatial summary by easting/northing bin and a simple trend check;
- decide constant offset versus per-tile correction.

Stability gate: proceed only if the per-tile medians are sufficiently consistent and the
spatial pattern does not indicate a large systematic gradient. “Sufficiently” must be
defined and reported before the corrected product is produced. A suggested screen is at
least 80% of tiles within ±0.15 m of the sample median and no monotonic easting/northing
trend larger than 0.10 m across the city. If the gate fails, stop at a revised control
report.

## P51.1 Citywide control sample and spatial estimate

- Add deterministic tile selection and manifest writer.
- Download/verify the selected sample.
- Extend the P50 control output with per-tile and spatial summaries.
- Report the gate decision.
- No corrected product yet.

Acceptance: 30–50 tiles selected and checked; control output is reproducible; per-tile
spatial variation and uncertainty are reported; gate decision explicit.

## P51.2 Versioned corrected P43 screen

Only if P51.1 passes.

- Apply the control correction to the P43 earlier grid.
- Write a new product directory, for example
  `change_vancouver_2018_2022_citywide_2m_control/`.
- Do not overwrite `change_vancouver_2018_2022_citywide_2m/`.
- Report net/gain/loss, height change, valid overlap, and control uncertainty.
- Label the product as a corrected screen, not a final citywide direction.

Acceptance: new product is reproducible; original product remains; corrected and original
differences are documented.

## P51.3 P44/P46 refresh and API/doc integration

Only if the corrected product is stable and documented.

- Rebuild P44 action labels and P46 turnover from the corrected product where supported.
- Add/describe the corrected product in the API/change-product index.
- Update P43/P44/P45/P46 docs with the new evidence.
- Preserve non-final caveats.

Acceptance: downstream products no longer silently inherit the unsupported +1.0 m
assumption; APIs/docs identify the corrected version; no unsupported claim.

## P51.4 Browser/dashboard verification and close-out

- Dashboard gates.
- Browser smoke if API/map changes.
- Final report, PR, approval, merge.

## Risks

- Browser downloads may fail or be interrupted; checksums and resumability are required.
- Larger tiles increase disk/time; sample selection must record size.
- Ground surfaces can change; class-2 control is not survey control.
- Spatial variation may invalidate a constant offset.
- A negative or inconclusive result is acceptable and must not be hidden.
- Downstream refresh can create false precision; versioned products and labels are required.
