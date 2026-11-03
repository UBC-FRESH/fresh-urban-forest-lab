# Plan: observed change, uncertainty, validation, and calibration

Status: active plan, 2026-11-03.

## Why this plan

The prototype currently demonstrates **scenario change**: it can grow, remove, replace,
and plant trees and show what a model says might happen. It does not yet demonstrate
**observed change**: what actually happened between two LiDAR acquisitions, with the
method differences and inventory uncertainty made visible. Andrew's core question is the
second one.

This plan closes that gap before a public release.

## Workstream 1: Observed change product

### Goal

A reproducible change product for:

- UBC campus: **LidarBC 2016 ↔ UBC LiDAR 2021**.
- Metro Vancouver street grid: **City of Vancouver 2018 ↔ 2022** where the tiles are
  accessible.
- Optional: UBC 2015 ↔ 2021 if the Abacus product can be retrieved.

### Outputs

A change directory added to a dataset:

- `change.json`: earlier/later labels, CRS, bounds, threshold, metrics, legend, overlap.
- `change.png`: transparent class overlay: loss, stable canopy, gain, no canopy.
- `change_grid.npz`: class grid, earlier/later canopy, elevation, valid mask.
- A `Change` tab in the web app with a georeferenced overlay and summary cards.

### Method

1. Acquire earlier point-cloud tiles for the same AOI.
2. Build an earlier CHM on the later DEM grid:
   - bin the highest non-ground return per cell;
   - subtract the later DEM;
   - use `NaN` outside the earlier tile coverage.
3. Build the later CHM on the same grid.
4. Compare only cells valid in both dates.
5. Report:
   - gain, loss, stable canopy, net change;
   - gain/loss as a share of earlier canopy;
   - mean height change on stable canopy;
   - valid overlap area.
6. Record the acquisition dates, vertical datum, threshold, and source tiles.

### Acceptance

- `fresh-urban-forest build-change` writes the three product files.
- `/api/change` and `/api/change.png` return them.
- The Change tab shows the overlay and the metrics.
- A method note states that the result is a thresholded CHM comparison, not a growth rate.
- The first UBC product runs on real tiles and the metrics are recorded in the changelog.

### Current status

- `build_change_product`, `/api/change`, `/api/change.png`, and the Change tab are
  implemented.
- The first UBC product uses LidarBC 2016 core tiles and the UBC 2021 CHM; a second uses
  UBC 2015 tiles. The Change tab can switch between them.
- Three products now use the same 2 km core mask at 1 m:
  2015→2016 net −12,016 m²; 2015→2021 net +111,166 m²; 2016→2021 net +123,182 m².
- The near-zero one-year change is the main sanity check; the five-to-six-year products
  both show a net gain.
- The City 2018↔2022 product is now available too; the tile host was bypassed with a
  headed browser under Xvfb.
- Caveat: the 2016 and 2021 vertical datums and acquisition seasons differ; the result is
  a screening product, not a calibrated growth estimate.

## Workstream 2: Inventory completeness and uncertainty

### Current status

- `inventory_completeness`, `/api/completeness`, measured/imputed flags, and the sidebar
  completeness panel are implemented.
- Demo completeness: DBH 53%, height 53%, crown width 54%, species 97% of 4,861 live
  trees.

### Goal

Make it impossible to read a canopy-volume or carbon number without seeing how much of it
rests on measured versus imputed tree attributes.

### Tasks

- Add `measured_fields` or per-attribute flags to `TreeRecord`.
- Add a completeness summary to the dataset manifest:
  - share with DBH, height, crown width, species, native flag;
  - share imputed from CHM or allometry.
- Show completeness cards and a “measured only” filter in the UI.
- Add a per-tree confidence class:
  - `measured`: DBH and height present;
  - `partial`: one measured, one imputed;
  - `location-only`: both imputed.
- Make scenario metrics report the confidence mix of the edited population.

### Acceptance

- A completeness panel is visible on the dashboard.
- The tree inspector says which fields are measured and which are imputed.
- A scenario can be run on measured-only trees.
- The data note states the completeness rate of the source.

## Workstream 3: LiDAR detection validation

### Current status

- `validate-detection` and `validation.py` are implemented.
- First core-campus run: 12,715 detected crowns, 4,861 inventory trees, 2,764 matches,
  precision 0.217, recall 0.569, F1 0.315, mean height bias +1.78 m, RMSE 5.04 m.
- Tuned run: `min-height=3`, `window=6` gives 9,678 detected, 2,314 matches, precision
  0.239, recall 0.476, F1 0.318 on the full core; the Main Mall patch reaches F1 0.366.
- The detector over-segments; the inventory is incomplete. A Main Mall field packet is
  generated (200 inventory trees, 3,966 detected crowns, 1,268 matches) and ready for
  field verification.

### Goal

Assess `detect_trees` against the UBC inventory instead of presenting it as a plausible
method.

### Tasks

- Match detected crowns to inventory trees by nearest centroid within a distance tolerance.
- Report precision, recall, F1, height bias, crown-radius bias, and missed-tree examples.
- Stratify by species group and canopy density.
- Write a validation report and a small GeoJSON of matched/unmatched crowns.
- Add a field-validation protocol for a sample of campus trees.

### Acceptance

- The report has a confusion matrix and bias estimates.
- The UI or report names the tolerance and the matching rule.
- At least one real UBC tile is assessed.

## Workstream 4: Local growth calibration

### Current status

- `fit-allometry` and `calibration.py` are implemented for height-diameter curves.
- Local fits reduce height RMSE versus the generic profiles, but R² is modest and annual
  growth still needs repeat measurements.
- The fit is recorded in `notes/reports/detection-and-allometry-2021.md`.
- True growth calibration is blocked by data: 9,322 unique UBC tree IDs, zero with more
  than one measurement date. See `notes/reports/growth-calibration-readiness.md`.

### Goal

Replace the generic growth curve with a local, uncertainty-aware model where the data
support it.

### Tasks

- Use repeat UBC inventory measurements where the same tree has multiple measurement
  dates.
- Fit height–diameter and annual DBH increment models by species group.
- Compare with the generic model, `fresh-fvsbc`, and i-Tree-style assumptions.
- Record the calibration data, fit diagnostics, and domain of applicability.
- Keep the generic model as the fallback for species with too few observations.

### Acceptance

- A calibration report lists coefficients, sample sizes, and diagnostics.
- The scenario projection can select `generic` or `calibrated` growth.
- The UI says which model produced a projection.

## Workstream 5: Release after the evidence

### Goal

Tag and publish only after the change and uncertainty story is defensible.

### Tasks

- Write release notes with the change-product method and caveats.
- Add the completeness and validation results to the public docs.
- Check Pages, demo, and clean clone.
- Tag v0.2.0 and publish.

## Order of work

1. Finish the observed-change product and UI (this change set).
2. Add inventory completeness and confidence flags.
3. Run the detection validation on the UBC 2021 tile and inventory.
4. Fit the first local growth calibration.
5. Release v0.2.0.

## Risks

- **Datum and season mismatch**: a raw CHM difference can be larger than the real change.
  Mitigation: record datums and acquisition dates; run threshold sensitivity; restrict
  claims to screening.
- **Sparse inventory**: UBC has many location-only records. Mitigation: confidence classes
  and measured-only views.
- **Tile coverage**: a change product is only valid where both dates overlap. Mitigation:
  report valid overlap area and mask outside it.
- **City tile access**: `webtransfer.vancouver.ca` may block automated clients. Mitigation:
  allow a user-supplied tile directory and record the manual retrieval.
- **Model overreach**: generic growth is not a local calibration. Mitigation: label the
  model and keep the fallback.

## Definition of done

The project can show an observed UBC canopy-change map, state the valid overlap, separate
measured from imputed tree attributes, and report detection accuracy. Only then does the
release claim “urban-forest change decision support” honestly.
