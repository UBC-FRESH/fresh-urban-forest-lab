# P50 canopy-change vertical control and uncertainty

Parent issue: #266
Planned branch: `feature/p50-vertical-control`
Status: pr-open

## Why

P43 compares 2018 and 2022 LiDAR surfaces. P45 showed that the citywide net sign is not
stable across a ±1 m vertical offset: from **−99 ha to +488 ha**. That is a stated
limitation, not a result that more visualization can fix.

P50 tests whether independent vertical control can resolve the direction. It is
feasibility-first: if public data cannot support a control estimate, the phase stops and
P45's warning remains.

## Scope

- Inventory 2018/2022 surfaces, ground classes, buildings, roads, and external references.
- Estimate vertical bias and scale on stable control surfaces, not canopy.
- Propagate the control uncertainty through P43/P45.
- Re-evaluate the citywide net direction only if the control supports it.
- Update P44/P46 language only where the new evidence supports it.
- Keep the result a screening comparison, not a survey-grade accuracy assessment.

## Out of scope

- New field work, field validation, or a field team.
- A full survey-grade LiDAR accuracy assessment.
- Tree survival, ownership, planting, policy, or causal claims.
- New UI polish or scenario work.
- Claiming a citywide gain/loss without defensible control.

## Feasibility gate

P50.1 must explicitly answer:

1. Are 2018 raw LAS tiles local, reproducible, and usable?
2. Are there stable non-canopy surfaces in both epochs: ground class 2, building roofs,
   road surfaces, or fixed infrastructure?
3. Is there an independent public vertical reference such as ICESat-2, GEDI, a provincial
   geodetic benchmark, or a surveyed control surface?
4. Can a spatially distributed sample produce enough paired observations for a robust
   offset estimate?

If the answer to 1 or 2 is no, stop. If only an external reference is missing, proceed with
stable-surface control and label it as such. Do not use canopy as the control.

## P50.1 Vertical-reference inventory and feasibility gate

- Inventory local 2018/2022 files, CRS, vertical datums, sizes, and availability.
- Inventory the City 2018 tile index and the 2022 DEM/DSM/CHM and building/road products.
- List candidate external references and what would be needed to use them.
- Recommend a small, spatially distributed tile sample for P50.2.
- Write a go/no-go report with explicit missing data.
- No estimate or citywide claim in this task.

Acceptance: a dated inventory report names local, external, and missing inputs; the
feasibility gate is explicit; no code is added unless the gate passes.

## P50.2 Stable-surface control extraction and offset estimate

- Download or use a documented sample of 2018 tiles.
- Extract ground class 2 and building class 6 points.
- Pair with 2022 DEM/DSM at the same coordinates and vertical datum.
- Use robust offsets on spatially distributed stable surfaces.
- Estimate horizontal/vertical scale if the data support it; otherwise estimate a constant
  offset only.
- Report sample counts, spatial coverage, outliers, and bootstrap uncertainty.
- Do not use canopy or tree points as control.

Acceptance: the offset estimate is reproducible from documented inputs; controls are
stable surfaces; uncertainty is reported; no full-city offset is claimed from an
unrepresentative sample.

## P50.3 P43/P45 re-evaluation with propagated uncertainty

- Apply the measured offset and uncertainty to the P43 2018 surface.
- Recompute net, gain, loss, and P45 sensitivity using the control-derived range.
- Compare with the prior arbitrary ±1 m envelope.
- State whether the sign is resolved, still unstable, or indeterminate.
- Update P44/P46/change-product language only if the result supports it.

Acceptance: the citywide direction is reported with explicit uncertainty; P45's warning is
retained if unresolved; no survival or causal claim is added.

## P50.4 Docs, report, and close-out

- Add a method report and update the change-product reference.
- Run dashboard and final checks.
- Open a PR and wait for explicit merge approval.
- If the gate fails, close with an inconclusive result and retain existing claims.

## Data inventory targets

Local:

- P43 2018 raw tile index: `data/raw/tiles/vancouver_2018_city.json`
- P43 2018/2022 processed change products and CHMs
- P30 2022 `dem.tif`, `dsm.tif`, `chm.tif`, `building_mask.tif`, roads, buildings
- P45 sensitivity product

External candidates:

- City of Vancouver 2018 LiDAR tiles (181 ZIPs; webtransfer links)
- ICESat-2 ATL03/ATL08 ground/height samples
- GEDI L2A ground/height samples
- BC geodetic control/benchmarks, if usable and licensed
- City building footprints and stable roof surfaces

No external dataset is assumed available until P50.1 records its access and licence.

## Testing

- Synthetic offset recovery for the robust estimator.
- Outlier, low-sample, and missing-control cases.
- Reproducibility from a documented sample.
- No use of canopy as control.
- P43/P45 invariants and dashboard gates.

## Risks

- 2018 raw tiles may be unavailable or blocked; the phase may stop at the gate.
- Building roofs change; ground can be excavated or filled.
- Different acquisition seasons, point density, classification, and datum handling remain.
- A small sample may not represent the city.
- A negative or inconclusive result is acceptable and must not be hidden.
