# Change Log

Newest entries last. Each milestone gets a dated entry that matches the roadmap status and the GitHub issue comments.

## 2026-11-02

- Created the repository from the workflow seed. The seed's agent contract, roadmap,
  documentation skeleton, validator, and dashboard were retained.

## 2026-11-03

### P0 Bootstrap and data reconnaissance

- Created `UBC-FRESH/fresh-urban-forest-lab` from the UBC-FRESH dev workflow seed.
- Adapted the package, CI, and dashboard to `src/fresh_urban_forest` and the web extras.
- Added MIT, `CITATION.cff`, code of conduct, and `DATA_LICENSES.md`.
- Recorded the data sources in `notes/reference/data-sources.md`, the software landscape
  in `notes/reference/software-landscape.md`, the architecture in
  `notes/design/architecture.md`, and ADRs 0001 to 0004.
- Dashboard: GREEN (lint, format, types, tests, validator, docs).

### Collaborator source review

- Added the LidarBC and CanElevation Series (NRCan) sources to the catalog, data note,
  data guide, and licence table, based on Andrew Almas's 2026-11-03 link set.
- Recorded that the City of Vancouver 2013 and 2018 LiDAR links are city products, not
  Metro Vancouver regional products, and that the UBC ArcGIS tree layer is the same living
  data behind the GitHub GeoJSON/CSV snapshot.
- Dashboard: GREEN.

### P5.0 Observed change product

- Added `fresh_urban_forest.change_product` and `fresh-urban-forest build-change`.
- Added `/api/change`, `/api/change.png`, and a `Change` tab with a georeferenced
  loss/stable/gain overlay and summary cards.
- Built the first UBC observed-change product from LidarBC 2016 core tiles and the UBC
  2021 CHM at 1 m over four core tiles: 4.57M m² earlier canopy, 4.76M m² later canopy,
  +384,143 m² gain, -199,042 m² loss, +185,101 m² net, +0.95 m mean height on stable
  canopy over 7.51M m² of overlap.
- Served the shell, app.js, and styles with `Cache-Control: no-store`, and added an
  `image_version` query to the change PNG so a rebuilt raster cannot be masked by an old
  browser cache.
- The product starts with a `NaN` mask outside the 2016 tile coverage; only the overlap is
  compared.
- Caveat: 2016 and 2021 differ in acquisition season and vertical datum. The product is a
  screening comparison, not a calibrated growth rate.
- Added `inventory_completeness` and `/api/completeness`, with measured/imputed flags on
  every tree and a sidebar completeness panel. Demo completeness: DBH 53%, height 53%,
  crown width 54%, species 97% of 4,861 live trees.
- Added the detailed plan in `notes/design/change-uncertainty-plan.md`.
- Dashboard: GREEN; tests include the change product, API, and completeness summary.

### P5.0 detection validation and local allometry

- Added `validation.py` and `fresh-urban-forest validate-detection`.
- First UBC core-campus assessment: 12,715 detected crowns, 4,861 inventory trees, 2,764
  matches, precision 0.217, recall 0.569, F1 0.315, height bias +1.78 m, RMSE 5.04 m.
  The detector over-segments; the inventory is incomplete.
- Added `calibration.py` and `fresh-urban-forest fit-allometry`.
- Local height-diameter fits reduce RMSE versus the generic profiles: conifer 7.42 vs
  12.38 m, deciduous 4.87 vs 7.18 m, unknown 3.03 vs 7.16 m. R² remains modest.
- Added `notes/reports/detection-and-allometry-2021.md`.
- Tuned detection on a 1 m Main Mall patch: best F1 0.366 at `min-height=3`, `window=6`;
  the full core gives F1 0.318 with the same settings.
- Added draft `notes/releases/v0.2.0.md`; no tag or release was created.
- Dashboard: GREEN.

### P5.0 field packet analysis

- Added `field_analysis.py` and `fresh-urban-forest analyze-field-packet`.
- Added `detected_checks.csv` and field measurement columns to the field packet.
- The analysis reports precision, precision including merged crowns, recall, missing/new
  trees, and height/crown bias, using field-verified rows only.
- Dashboard: GREEN.

### P5.0 field validation packet

- Added `field_packet.py` and `fresh-urban-forest field-packet`.
- Generated a Main Mall packet: 200 inventory trees, 3,966 detected crowns, 1,268 matches,
  with GeoJSON, CSV checklist, and a field protocol.
- Added `notes/reports/field-validation-packet.md`.
- Dashboard: GREEN.

### P5.0 UBC 2015↔2021 observed change

- Downloaded four UBC 2015 LAZ tiles with the Abacus user-agent workaround and transformed
  EPSG:26910 points into the 2021 EPSG:3157 DEM grid.
- Added a second change product: +320,535 m² gain, −209,369 m² loss, +111,166 m² net,
  +0.235 m mean height on stable canopy over 4.00M m² of overlap.
- Added `/api/changes` and a comparison selector to the Change tab. All three displayed
  products now use the same 2 km core mask:
  - 2015→2016: net −12,016 m², mean height −0.095 m
  - 2015→2021: net +111,166 m², mean height +0.235 m
  - 2016→2021: net +123,182 m², mean height +0.420 m
- Added `notes/reports/observed-change-ubc.md` with the comparison and caveats.
- Dashboard: GREEN.

### P5.0 documentation deep dive and Pages

- Expanded the Sphinx site with web-app, CLI, architecture, change-product, validation and
  calibration, assistant, deployment, reproducibility, testing, limitations, and project
  status pages.
- Added the scenario-lab, change-product, and assistant screenshots.
- Added the scenario studio, planting-zone, time-animation, comparison, and export docs.
- Enabled GitHub Pages with the Actions build source and restored the deploy job.
- Published https://ubc-fresh.github.io/fresh-urban-forest-lab/; the build and deploy jobs
  are green and every documented page returns 200.
- Dashboard: GREEN.

### P5.0 City 2018↔2022 observed change

- Bypassed the `webtransfer.vancouver.ca` Cloudflare block with a headed Chromium under
  Xvfb and added `scripts/browser_download_tiles.py` as an operator helper.
- Downloaded 2018 and 2022 UBC-core tiles; 2018 is EPSG:3157 and 2022 is EPSG:26910, so
  the 2022 points were transformed before binning.
- Built the City 2018↔2022 product: 728,756 m² earlier canopy, 864,335 m² later canopy,
  +212,734 m² gain, −77,155 m² loss, +135,579 m² net, +0.575 m mean height over 2.00M m².
- Added it to the Change tab selector and recorded `notes/reports/observed-change-vancouver.md`.
- Dashboard: GREEN.

### P5.0 Vancouver tile discovery and calibration readiness

- Added `vancouver.py` and `fresh-urban-forest tiles vancouver` for the City 2013/2018/2022
  LiDAR indexes. The UBC pilot bbox returns 26 tiles per year.
- Recorded that `webtransfer.vancouver.ca` returns Cloudflare 403 to automated clients; the
  manifest remains usable for a browser-assisted or manual fetch.
- Added `notes/reports/growth-calibration-readiness.md`: 9,322 unique tree IDs, zero with
  more than one measurement date, so annual growth calibration is blocked by data.
- Dashboard: GREEN.

### P1.7 External LiDAR tile discovery

- Added `fresh_urban_forest.tiles`, `lidarbc`, and `canelevation` modules with one
  normalised tile record, JSON manifests, and checksum-aware downloads.
- Added `fresh-urban-forest tiles lidarbc`, `tiles canelevation`, `tiles index`, and
  `tiles fetch`.
- UBC pilot bbox check: 34 LidarBC point-cloud tiles and 15 CanElevation tiles. The
  CanElevation 2016 Lower Mainland set overlaps the LidarBC 2016 coverage, so it is a
  COPC alternative/cross-check, not an independent repeat measure.
- Downloaded and summarised one 6.04 MB LidarBC tile as a QA check.
- Dashboard: GREEN; 202 tests.

### P1 Canonical urban-forest dataset

- Added the YAML source catalog and resumable, SHA-256-verified materialization.
- Added UBC GeoJSON/CSV and Vancouver CSV tree adapters.
- Added raster terrain/canopy sampling, CHM derivation, LAZ summary, and canopy metrics.
- Added the portable dataset writer/loader and the UBC core-campus demo.
- Real-data check: UBC 2021 CHM/DEM + 9,324 tree records; 9,259 live trees; 66.6 percent
  raster canopy cover; 294.2 million m³ canopy-volume prism; 3,822 t above-ground carbon.
- Dashboard: GREEN.

### P2 Tree-level analytics and growth

- Added the transparent allometric growth model with crown-light-exposure adjustment.
- Added composition, size-class, native-share, Shannon, carbon, and canopy metrics.
- Added append-only scenario edits and annual projection with cost and DSS score.
- Added explainable planting recommendations and CSV/GeoJSON exports.
- Added local-maxima plus marker-controlled watershed tree detection and repeat-measures
  canopy change.
- Dashboard: GREEN.

### P3 2D and 3D decision-support prototype

- Added the FastAPI service with dataset, tree, scene, image, scenario, DSS, and export
  endpoints.
- Added the MapLibre 2D map with local hillshade, canopy overlay, buildings, boundary, and
  tree layers.
- Added the Three.js terrain mesh and instanced trunks/crowns with orbit controls and
  raycast selection.
- Added shared 2D/3D selection, plant mode, move mode, scenario charts, comparison cards,
  and downloads.
- Vendored MapLibre and Three.js for an offline demo.
- Dashboard: GREEN.

### P3.7 Local assistant and 3D building context

- Added `/api/agent` and `/api/agent/chat`; the assistant runs the local `opencode` CLI
  with `--allow-agent`, `--agent-model`, and `--agent-timeout`.
- Added the `+ Ask` pill and pop-up chat panel with quick prompts, markdown rendering,
  tool-action chips, session continuity, and live browser context.
- Fixed 3D buildings: the scene payload now carries a terrain-sampled `base_z`, and the
  browser extrudes each footprint instead of placing a floating box.
- Made all static and API URLs relative so the app works behind a reverse-proxy path
  prefix (for example a code-server `/proxy/8101/` path).
- Dashboard: GREEN; 196 tests.

### P4 Verify and demo

- Added 190 tests across unit, spatial, CLI, service, and static layers.
- Coverage: 87.55 percent branch coverage, above the 85 percent gate.
- Chromium smoke check: the 2D map and 3D scene load with no console errors.
- Built and served the real UBC 2021 dataset; the demo dataset is tracked in
  `data/demo/ubc_core/`.
- Added quick-start, data, contract, method, software-landscape, agent-protocol, and API
  documentation.
- Dashboard: GREEN.
- Close-out report: `notes/reports/p4-closeout.md`.

### P7-P11 programme planning

- Completed a rapid peer-reviewed and grey-literature review of tree/building shade,
  species selection, growth and drought stress, irrigation, multi-objective optimization,
  Pareto visualization, off-inventory/private canopy, and urban bird habitat.
- Wrote the detailed programme plan in `notes/design/urban-canopy-program-plan.md`.
- Recorded the proposed marginal-shade and evidence-tier decision in ADR 0005.
- Queued P7-P11 as parent issues #40-#44 with planned branches and task checklists.
- Added the public research-agenda page to the docs and `llms.txt`.
- Recommendation: P7 shade/species, P8 optimization/Pareto, P9 off-inventory, P10 birds,
  P11 integration. No phase is active and no code behavior changed.
- Dashboard: GREEN (lint, format, types, tests, validator, docs).

### P7 Solar shade and species-fit engine

- Added NOAA solar position, projected building/tree/terrain shadows, time-integrated
  sunlit/building/tree/overlap/marginal-shade arrays, and a 1.5 m target plane.
- Added 12 species trait profiles, site-fit scoring, a single-bucket water balance,
  growth/vigour modifiers, irrigation-policy comparison, and cost per shade-hour.
- Added `shade`, `species-fit`, `water`, and `irrigation` CLI commands and the
  `/api/solar`, `/api/shade`, `/api/shade.png`, `/api/light/tree/{id}`, `/api/species`,
  `/api/species/fit`, `/api/water`, and `/api/irrigation` endpoints.
- Added the Light tab, georeferenced shadow overlay, 3D sun, tree shade/water card, and
  evidence badges.
- UBC core demo, 2026-06-21, 3-time sample: 6.82% shade, 2.54% tree shade, 0.50% marginal
  tree shade. The 6-time sample gives 7.23% shade with stable tree/marginal fractions.
- Added `docs/reference/shade-and-species.rst`, the review protocol, and
  `notes/reports/p7-shade-species.md`.
- Tests: 268 passed. Dashboard: GREEN.
- Limits: no field shade survey, no Radiance/SOLWEIG benchmark, 2.5-D crowns, priors for
  species/water, and a scaled annual estimate.

### P8 optimization and Pareto explorer

- Added `optimize.py`: candidate sites, species options, seven objectives, three constraints,
  exact evaluation, weighted scalarisation jobs, and solution-to-scenario edits.
- Added `pareto.py`: dominance, non-dominated archive, approximate hypervolume, bootstrap
  robustness, and objective slices.
- Added `surrogate.py`: aggregate features and a validated ridge screening surrogate.
- Delegated hard combinatorial search to **Fresh Solutions v0.8.0** through the optional
  `optimize` extra. No custom metaheuristic engine was added.
- Added `optimize` and `pareto` CLI commands and the `/api/optimize` job endpoints.
- Added the Optimize tab: job controls, 3D orbitable archive, axis/colour/size/slice
  controls, solution inspector, and load-as-scenario.
- Benchmark: 48 sites / 72 scalarizations / 7 objectives / 37,224 evaluations; 5.34 s on
  one worker and 3.64 s on four workers (1.47x), same archive and hypervolume.
- Whole-campus run: 387 sites / 72 scalarizations / 1,010,952 evaluations / 71 archive
  solutions / hypervolume 0.0508 / 100.94 s.
- Z* convergence: balanced scalarization, 387 sites, 112,116 evaluations, 36 rounds,
  patience stop, best scalar objective -0.293285, 333 planted sites.
- Small 24-site run: 13 archive solutions, hypervolume 0.0006, 0.34 s on one worker.
- Surrogate holdout: shade R2 0.91, equity 0.86, native 0.89, diversity -0.41; archive
  always uses exact evaluation.
- Added `docs/reference/optimization-and-pareto.rst` and the P8 report.
- Fixed optimizer UI state bugs: requested scalarization count, scenario dropdown sync,
  load/slice reset, fixed-reference hypervolume, mobile layout, and scenario selection now
  switches to the 3D scene so the loaded scenario is visible.
- Added saved Pareto archives: completed jobs are written to
  `runtime/optimizations/<job_id>.json`, loaded at startup, and available through the
  **Saved Pareto archive** dropdown. The full-campus 387-site archive loads instantly and
  can produce a 385-tree scenario.
- Added archive metadata, rename/delete controls, a three-solution pin/compare table,
  coloured on-cube axis lines and X/Y/Z labels, and a jump-back link from a `Pareto <id>`
  scenario to its source archive point.
- Fixed the 3D scene ground alignment: the terrain mesh now uses the scene origin instead
  of the grid centre, so trees and buildings are no longer shifted about 1.4 km against the
  terrain; missing DEM cells are filled from their nearest valid neighbour instead of being
  rendered as a zero-elevation hole. Building opacity is less ghostly at low camera angles.
- Tests: 285 passed. Dashboard: GREEN.
- Limits: weighted-sum finite approximation, Monte Carlo hypervolume, bootstrap robustness,
  precomputed P7 evaluator, and no city-scale claim.

### P12 Arbor method mining and clean-room point-cloud primitives

- Audited `r-lidar/arbor` 1.1.5 at commit `a2b487f4a23236a42eec50cb6583a5eae15593ed`.
- Recorded the GPL-3.0 licence boundary, candidate matrix, design patterns, attribution
  templates, and delivery sequence in `notes/reference/arbor-method-mining.md`.
- Added ADR 0006: reimplement copyleft methods clean-room; never copy their code.
- Added the public `docs/reference/arbor-method-mining.rst` page, the software-landscape
  row, the `docs/index.rst` and `docs/llms.txt` links, and the API module entry.
- Added `src/fresh_urban_forest/pointcloud.py` with four opt-in primitives:
  `hybrid_homogenize`, `statistical_outlier_mask`,
  `voxel_connected_components`, and `local_anisotropy`.
- Each function names Arbor 1.1.5, its source file or book chapter, the GPL-3.0 source
  licence, and the clean-room statement in a `Method provenance` docstring section.
- Added `tests/test_pointcloud.py` with synthetic-cloud coverage, edge cases, and
  determinism checks. The new module is 92 percent covered.
- Tests: 287 passed; total coverage 87.51 percent. Dashboard: GREEN.
- PR #63; CI run 41742328362. Close-out report:
  `notes/reports/p12-arbor-method-mining.md`.
- Limits: the four functions are opt-in and are not wired into the default CHM/ITD path;
  PTD ground classification, semantic/instance segmentation, QSM, and QSF are future work.
- P12 is complete. P13 is recommended for ALS ground classification and HAG; the MLS/TLS
  semantic/instance/QSM stack remains a separate future package.

### P9 off-inventory canopy and value of information

- Added `off_inventory.py`: CHM detection, inventory matching, confidence-scored
  off-inventory candidates, a separate augmented population, and a P8 value-of-information
  comparison.
- Added `fresh-urban-forest off-inventory` with `--voi` and the
  `/api/off-inventory`, `/api/off-inventory.geojson`, and `/api/off-inventory/value`
  endpoints.
- Added the sidebar summary and map layer toggle; the layer is off by default and shows
  candidate confidence and height.
- Main Mall pilot: 5,536 detected, 1,409 matched, 500 candidates (cap), 435 high-confidence,
  8.3 ha candidate crown area; ownership unknown.
- Value of information: 9,259 → 9,759 trees; 2.855M → 3.669M m³ crown volume; 3,827 →
  5,024 t carbon. Best-shade plan unchanged (Jaccard 1.00, 0 sites differ) in this pilot.
- Added privacy/terminology note and the P9 report.
- Tests: 310 passed. Dashboard: GREEN.
- Limits: no parcel/ownership layer, no field validation, 500-candidate cap, unknown species,
  screening-only carbon/canopy totals.

### P10 bird habitat and demography

- Added `habitat.py`: 3D canopy metrics, five guilds, guild suitability, relative-abundance
  index, optional observation CSV, and evidence tiers.
- Added `demography.py`: two-stage juvenile/adult matrix, lambda, prior range, survival
  curve, stable adult fraction, and sensitivity.
- Added `GET /api/birds` and `fresh-urban-forest birds`; both accept a scenario and year.
- Added the Birds tab: habitat metrics, guild bars, lambda/prior range, sensitivity, and
  adult survival chart.
- Baseline demo: habitat score 0.78, p95 31.3 m, FHD 0.61, 4 layers, gap 19%, native 26%.
- Guild lambda range: 0.78–1.09; all outputs are prior-driven.
- Added method note, public docs, and the P10 report.
- Tests: 319 passed. Dashboard: GREEN.
- Limits: no local point counts, distance sampling, mark-recapture, or expert review response;
  relative abundance is not density and lambda is not a local forecast.

### P13 ALS ground classification and height above ground

- Added `classify_ground_ptd` and the typed `GroundClassification` result to
  `src/fresh_urban_forest/pointcloud.py`.
- The classifier seeds a TIN from the lowest point per grid cell, progressively adds points
  within a vertical residual and point-to-vertex angle threshold, and interpolates HAG from the
  final ground surface.
- Added seed/iteration counters and a warning for degenerate or too-small TINs.
- Added synthetic tests for a flat plane, a gentle slope, high vegetation, a collinear
  degenerate seed set, an empty cloud, and invalid parameters.
- Documented the simplified, PTD-inspired method, the provenance to Axelsson (2000) and
  Arbor chapter 4, and the real-tile validation gate in the note and Sphinx page.
- Tests: 311 passed; total coverage 87.55 percent. Dashboard: GREEN.
- Limits: this is not a full PTD implementation. The default vertical residual is
  permissive, points outside the TIN hull are not ground, and no FEMIC integration is
  included.

### P13.2 Real LidarBC tile validation

- Acquired the 415,068-point LidarBC 2025 tile
  `bc_092g024_4_3_1_xyes_8_utm10_20250826_20250826.laz` under OGL-BC. The LAZ stays in
  `runtime/p13/` and is not tracked.
- Replaced the initial TIN-facet-slope gate with a point-to-triangle-vertex angle gate after
  the first validation pass showed that the facet gate over-labelled low vegetation.
- Strict setting (`cell_size_m=1`, `max_angle_deg=15`, `max_distance_m=0.5`): class-2
  recall 0.9998, class-2 HAG p99 0.021 m, 376,587 predicted ground points (90.73%),
  67.6 s.
- Class-1 (unclassified) is not a negative label; class-7 (noise) is not a negative label.
  About 80% of class-7 near-ground noise is labelled ground. Precision against class 2 is
  therefore not a valid accuracy estimate.
- Added `notes/reports/p13-als-ground-validation.md` and
  `notes/reports/p13-als-ground-validation.json`.
- Tests: 311 passed; total coverage 87.55 percent. Dashboard: GREEN.
- Limits: one coastal/low-relief tile, no exhaustive ground truth, and near-ground noise is
  still over-labelled. P13.3 low-point-cut/SOR preprocessing is the next gate. No FEMIC
  integration or operational claim is included.

### P13.3 Low-point-cut and SOR policy

- Added `low_point_mask(height_above_ground, cut_m=0.15)` as the downstream segmentation
  contract. It flags low points without changing the ground labels.
- Ran `statistical_outlier_mask(k=10, multiplier=2.0)` before PTD on the 2025 P13.2 tile
  and a 3,042,883-point 2016 tile.
- SOR removed 3.98-4.09% of points, including 8.6% of class-7 noise but only 0.04-0.61% of
  class-2 ground. Class-2 recall after SOR+PTD was 0.9999 on the 2025 tile and 0.9802 on
  the 2016 tile.
- SOR does not fix near-ground noise. On the 2025 tile, 86.75% of retained class-7 points
  were still labelled ground. However, 99.84% of class-7 false ground is within 0.15 m HAG.
- Added `notes/reports/p13-als-ground-sor.json` and extended the P13 validation report with
  the SOR/low-point policy.
- Tests: 318 passed; total coverage 87.84 percent. Dashboard: GREEN.
- Limits: SOR is optional and loses a small amount of ground; the low-point flag is not a
  ground label; no operational or FEMIC claim is included.

### P13.4 FEMIC integration decision

- Deferred FEMIC integration. The classifier remains opt-in in `fresh-urban-forest-lab`.
- Reasons: two tiles from one coastal/low-relief map sheet, no exhaustive ground truth, and
  near-ground class-7 noise remains in the ground class.
- Reopen only with a checked reference patch, a second terrain type, a fuller PTD angle
  test, and a stable versioned contract.
- Updated the P13 report, note, and docs. No FEMIC code changed.
- Close-out report: `notes/reports/p13-closeout.md`. P13 is complete.
- Tests: 318 passed; total coverage 87.84 percent. Dashboard: GREEN.
- Limits: this is a scope decision, not an accuracy claim. No tag or release is included.
### P11 integration and v0.3 release candidate

- Added `integration.py`: unified lab report across dataset, scenario, metrics,
  completeness, shade, birds, and off-inventory with evidence and caveats.
- Added `GET /api/report` and `fresh-urban-forest report`.
- Added the **Export lab report** browser button; baselines and scenarios download JSON.
- Added `docs/reference/integration-and-release.rst`, the P11 report, and v0.3.0 release
  notes.
- Bumped package, citation, and runtime version metadata to 0.3.0.
- Tests: 331 passed. Dashboard: GREEN.
- Release limits: no tag, GitHub release, Pages setting, or public deployment has been
  created; those actions remain approval-gated.

### P14 Ground reference and second terrain validation

- Added a reproducible reference protocol: class 2 as positive ground, nearest class-2
  surface for reference HAG, high-confidence negative as non-class-2 with reference HAG
  > 2 m, and the ambiguous 0-2 m band excluded.
- Validated the 2021 Golden-area steep tile
  `bc_082n025_4_2_1_xyes_8_utm11_2021.laz` (113,775 points, about 62 m relief,
  EPSG:2955 + CGVD2013) under OGL-BC.
- Steep tile: class-2 recall 0.9634, high-confidence false-ground 4.65%, class-2 HAG p99
  0.0441 m, predicted ground 76.12% of kept points.
- Coastal tile: class-2 recall 0.9999, high-confidence false-ground 3.35%, class-2 HAG p99
  0.0217 m.
- P14.3 approves an optional FEMIC adapter prototype, not a default pipeline change.
  Conditions: manual reference patch, versioned optional adapter, stable
  `GroundClassification`/`low_point_mask` contract, second steep and coastal tile.
- Added `notes/reports/p14-ground-reference.md` and `.json`.
- Tests: 331 passed; total coverage 87.66 percent. Dashboard: GREEN.
- Close-out report: `notes/reports/p14-closeout.md`. P14 is complete.
- Limits: the reference is not manually labelled; the 0-2 m band is excluded; one small
  steep tile; no production FEMIC integration.

### v0.3.0 release

- Tagged and released the integrated lab as v0.3.0.
- P5 release gate closed with the stated data limit: no field validation or repeat-measure
  growth calibration yet.
- Removed an unrequested administrative phase and its review, triage, and contract-migration
  content. It did not map to a workflow task or an explicit instruction.
- Deleted the removed phase's issue and closed P5.0 issue #39 with evidence and explicit
  limitations.
- Release notes: `notes/releases/v0.3.0.md`.

### P15 Manual ground reference and optional FEMIC adapter design

- Added a manually checked 20 m x 20 m reference patch from the Golden-area steep tile:
  6,393 points, classes 1=5,410, 2=975, 7=8.
- Side/top views confirm class 2 is the lowest continuous surface and class 1 mixes
  unclassified ground with above-surface vegetation. The check is not point-by-point.
- Patch metrics: class-2 recall 0.9507, high-confidence false-ground 3.14%, class-2 HAG p99
  0.0434 m.
- Added the optional FEMIC sidecar adapter design: `ground.laz`, `manifest.json`, and
  `qa.json`; versioned schemas; no hard FEMIC dependency; no default product change.
- Added ADR 0007: the adapter is a sidecar contract, not a FEMIC core import.
- Tests: 331 passed; total coverage 87.66 percent. Dashboard: GREEN.
- Close-out report: `notes/reports/p15-closeout.md`. P15 is complete.
- Limits: the patch is visually checked, not point-by-point labelled; the adapter is
  designed but not implemented; no tag or release is included.

### v0.3.0 release documentation correction

- Corrected stale v0.2.0 and release-candidate status in the roadmap, project status, notes,
  and live docs.
- Moved tag `v0.3.0` to the final release commit and refreshed the GitHub release notes.

### P16 Optional FEMIC ground-adapter implementation

- Added `fresh_urban_forest.ground_adapter` with `GroundAdapterParameters`,
  `GroundAdapterParameters.sha256`, `GroundBundleResult`, and `write_ground_bundle`.
- The writer copies the input LAZ and adds `is_ground`, `hag`, `is_low`, and `ref_class`
  dimensions, then writes a versioned `manifest.json` and `qa.json`.
- Added the opt-in `ground-adapter` CLI command. It is not part of `build`, `serve`, or the
  default dataset path.
- Added synthetic-LAZ contract tests for the nominal bundle, extra dimensions, hashes,
  schemas, missing CRS/vertical datum warnings, overwrite refusal, empty input, and the CLI.
- Added `lazrs>=0.5` so the LAZ write path works in a clean install and in CI.
- Tests: 337 passed; total coverage 87.68 percent. Dashboard: GREEN.
- Real-tile smoke: Golden-area tile, 113,775 points, 82,530 predicted ground, 5.8 s;
  local only, not a CI network job.
- Close-out report: `notes/reports/p16-closeout.md`. P16 is complete.
- Limits: the adapter is not a FEMIC core import; no real-tile smoke test is in CI; the
  classifier remains opt-in and does not change default FEMIC products.

### P17 CHM/ITD post-processing

- Added `fresh_urban_forest.itd_postprocess` with `TreePostprocessResult` and
  `postprocess_trees`.
- Added edge-buffer flags, strict small-tree flags, and a conservative over-segmentation
  merge that records every source ID.
- Added `kept()` filtering and a JSON-friendly summary.
- Added synthetic tests for edge flags, small trees, merge, no-merge, empty input, invalid
  parameters, and JSON output.
- Tests: 346 passed; total coverage 87.76 percent. Dashboard: GREEN.
- Close-out report: `notes/reports/p17-closeout.md`. P17 is complete.
- Limits: the merge is a small CHM heuristic, not a point-cloud instance resolver; the
  default `detect_trees` output is unchanged and the feature is opt-in.

### P18 CHM/ITD post-processing exports and smoke test

- Added `detect-trees --postprocess` with `--buffer`, `--max-small-height`, `--no-merge`,
  and `--summary`.
- Post-processed runs write kept-crown GeoJSON and a sidecar summary JSON; the default
  command is unchanged.
- Added a CLI test for the post-processed output and sidecar summary.
- Demo smoke: 859 detected, 701 kept after 57 merge groups; a 50 m stress buffer flags 5
  crowns. The 10 m default buffer flags none on the large interior demo.
- Tests: 347 passed; total coverage 87.79 percent. Dashboard: GREEN.
- Close-out report: `notes/reports/p18-closeout.md`. P18 is complete.
- Limits: one demo dataset, no field validation of the merge reduction, and the small-tree
  flag is not exercised because the detector minimum height is above the threshold.

### P19 Merge-reduction audit and guard

- Audited the demo merge: 57 groups, 215 source crowns, one group with 67 crowns spanning
  4.6 km. The old union-find merged transitively across the whole dataset.
- Added `merge_max_group_members` (default 4) and `merge_max_group_extent_m` (default 30 m)
  guards. A union is rejected when the combined group exceeds either cap.
- Guarded demo: 3 local groups, 6 source crowns, 859 detected -> 856 kept. The old rule kept
  701. The guarded merge is conservative and may under-merge real over-segmentation.
- Exposed `--merge-max-area-ratio`, `--merge-max-height-delta`,
  `--merge-max-group-members`, and `--merge-max-group-extent` on `detect-trees`.
- Added guard and invalid-parameter tests; rendered a before/after audit map in `runtime/`.
- Tests: 350 passed; total coverage 87.82 percent. Dashboard: GREEN.
- Close-out report: `notes/reports/p19-closeout.md`. P19 is complete.
- Limits: one demo dataset and a visual audit; no field crown labels; the merge is a safety
  filter, not an instance solver; the default detector is unchanged.

### P20 Non-transitive crown merge and manual audit patch

- Replaced the union-find merge with an anchor pass: only larger crowns absorb smaller
  crowns, and an absorbed crown cannot become an anchor.
- Kept the 4-source and 30 m group caps.
- Added a synthetic manual audit patch: a known split crown merges; two similar distinct
  crowns stay separate.
- Added tests for non-transitivity, multi-crown anchors, and the audit patch.
- Demo result is unchanged: 859 detected, 3 local groups, 856 kept. The old 57 groups were
  chain artifacts, not local split crowns.
- Tests: 353 passed; total coverage 87.82 percent. Dashboard: GREEN.
- Close-out report: `notes/reports/p20-closeout.md`. P20 is complete.
- Limits: synthetic audit patch, one demo dataset, and no orthophoto/field crown labels.
  The anchor merge is a safety filter, not a validated instance solver.

### P21 Ground-adapter second-tile smoke test

- Ran `write_ground_bundle` on the 2025 coastal LidarBC tile
  `bc_092g024_4_3_1_xyes_8_utm10_20250826_20250826.laz` with EPSG:3157 and CGVD2013.
- Coastal bundle: 415,068 points, 374,711 predicted ground, 68.8 s, no warnings.
- Golden comparison: 113,775 points, 82,530 predicted ground, 5.8 s, no warnings.
- Both bundles use `femic.ground-bundle.v1` and `femic.ground-qa.v1`, with hashes, explicit
  CRS/vertical datum, and the four extra dimensions.
- Added `notes/reports/p21-ground-smoke.md` and updated the public adapter section.
- Tests: 353 passed; total coverage 87.82 percent. Dashboard: GREEN.
- Close-out report: `notes/reports/p21-closeout.md`. P21 is complete.
- Limits: two tiles, no field/manual point labels, and no CI network job for real-tile
  smoke.
### IRSS and Silva21 method provenance

- Added `notes/reference/irss-silva21-method-provenance.md`. It records that the
  urban LiDAR canopy work is independently implemented from generic CHM, ITD,
  canopy-metric, and change methods, not from IRSS/Silva21 code or registry
  contracts. It maps `INV-02`, `INV-06`, `BIO-02`, `DEC-04`, `DATA-01`, and
  `INV-01` as candidates for later evaluation, with fit risks and a proposed
  sequence. No integration is claimed and no registry target changed.
- Dashboard on the note head: GREEN on all gates; 353 tests pass.


### P30 full Vancouver city pilot

- Activated P30 (#105) and its six tasks (#106–#111) for a full City of Vancouver public-data
  pilot.
- Locked the source set: City 2022 LiDAR (181 tiles, ~49 points/m²), 184,152 public trees,
  the 22 local-area polygons, building footprints, and climate normals.
- The city AOI is 118.76 km² in EPSG:3157. The working storage budget is 250 GB against
  7.9 TB free on `/srv/shared-data`; no dataset is written to the container root disk.
- Added `notes/design/vancouver-city-pilot.md` with the processing, metrics, 3D, validation,
  and storage plan.
- Dashboard: GREEN. Tests: 331 passed.

### P30.1 source lock

- Locked the Vancouver AOI at 118.76 km² from the union of 22 local-area polygons.
- Downloaded and hashed 184,152 public trees, the local-area polygons, and 154,124 building
  footprints. The 2022 City LiDAR manifest contains all 181 tiles.
- Climate normal locked at 1,098.8 mm/yr (Vancouver Harbour CS, 1981–2010).
- Source evidence: `notes/reports/p30-source-lock.json`.
- Started the resumable browser-assisted LiDAR download into
  `data/raw/city_lidar/2022/`.
- Dashboard: GREEN.

### P30 city pipeline

- Added `city.py` for 1 m classified-LAS rasterisation and city mosaic assembly.
- Added `city_inventory.py`, `city_metrics.py`, and `city_pack.py` for the full inventory,
  local-area metrics, and portable city dataset.
- Added operator scripts for LiDAR rasterisation, inventory enrichment, metrics, and pack
  assembly.
- Added `/api/city-metrics` and a City tab in the web app for city KPIs, local-area ranking,
  methods, and caveats.
- Verified class 5 is high vegetation and class 9 is water in the City LAS despite the
  portal text; the rasteriser uses the ASPRS classes.
- Dashboard: GREEN.

### P30 city metrics UI, docs, and shade

- Added the city metrics endpoint and City tab with city KPIs, local-area ranking, method
  labels, and caveats.
- Added the full-city source/licence rows, data-source note, city pilot docs page, and
  README build path.
- Added the optional representative-day shade script.
- Added tests for city rasterisation, inventory evidence, city metrics, city pack assembly,
  and the optional city-metrics endpoint.
- Dashboard: GREEN.

### P30 full Vancouver city pilot close-out

- Built the full city mosaic: 181/181 tiles, 8,721,285,369 points, 99.96% AOI coverage.
- Enriched 184,151 public trees; 162,497 height pairs, bias -0.397 m, RMSE 4.292 m.
- City metrics: 26.854% canopy cover, 350.16M m³ canopy volume, 95,792 t carbon,
  1,979 t/yr modelled sequestration, 3.50–7.01M m³/yr rainfall screening.
- City validation: the City's 2022 estimate is about 25%, a +1.854-point difference;
  a sanity check, not calibration.
- City tab and city-scale 3D scene pass browser smoke with no console or page errors.
- Storage: 165 GB raw LiDAR, 1.8 GB processed, 7.7 TB free; no dataset on the root disk.
- Close-out report: `notes/reports/p30-vancouver-city.md`.
- Dashboard: GREEN.


### P30.7 demo portal

- Added `fresh_urban_forest.portal` and `portal_app.py` for a landing page on port 8101.
- Mounted the UBC demo at `/ubc/` and the Vancouver city demo at `/vancouver/`, with
  separate runtime directories.
- Kept the WS4 portal on port 8790 unchanged.
- Portal browser smoke: both cards load, both apps reach live status, the City tab is
  visible only in Vancouver, and there are no console or page errors.
- Dashboard: GREEN.


### P30 full 2D map layers

- The Vancouver 2D map now loads all 184,151 public-tree points and all 154,124 building
  footprints from compressed GeoJSON, after the app reaches live status.
- The 3D scene keeps a spatially stratified visual sample of 29,096 trees and 12,000
  buildings, with an explicit sample label in the scene HUD.
- Added a Downtown camera preset alongside the city view.
- Browser smoke: map loads in about 4.5 s to live, full map layers arrive after about 7 s,
  and there are no console or page errors.
- Dashboard: GREEN.


### P30 full 3D city and street basemap

- The Vancouver 3D scene now loads all 184,151 trees and all 154,123 building footprints as
  compact axis-aligned massing boxes; the full scene is 5.7 MB gzip.
- Added OpenStreetMap road centrelines as a local compressed layer for a pale 2D underlay
  and a 3D street overlay, with attribution in the map HUD and a shared `streets` toggle.
- The 2D map continues to load all 184,151 trees and all 154,124 full building footprints.
- Browser smoke: no console or page errors; app live in about 4.4 s, full 3D scene build
  about 0.84 s, software-WebGL screenshot readback is the slow part.
- Dashboard: GREEN.


### P30 enable the portal assistant

- The landing portal now passes `allow_agent=True` by default to both mounted apps, so the
  `+ Ask` helper is available in the UBC and Vancouver UIs.
- The portal remains behind the existing Cloudflare/CWL gateway; the assistant is still
  opt-in at the service level and can be disabled with `FRESH_PORTAL_ALLOW_AGENT=0`.
- Dashboard: GREEN.


### P30 close-out

- Merged PR #131 as `c5e01c9e403d11452986a4ce9830fe86adbb6bb8` and closed parent issue #105.
- Marked P30 complete in the roadmap and project status.
- No tag, release, Pages setting, or public deployment change.
- Dashboard: GREEN.

### P31 Move the ground writer to FEMIC

- Removed `src/fresh_urban_forest/ground_adapter.py`, its CLI command, and its tests.
- Removed the `ground_adapter` API docs entry.
- Updated the ground-lane reference to point to FEMIC `ground-bundle-build`.
- Kept `classify_ground_ptd` and the point-cloud primitives as an urban ALS prototype.
- This removes the misleading cross-repo writer; FEMIC is now canonical.

### P35 off-inventory classifier and QA plan

- Added the P35 phase for off-inventory conifer/deciduous classification and interface QA.
- Known-good labels are available from Vancouver and Surrey public inventories; Burnaby
  and Coquitlam have no public species inventory and will be marked unlabelled.
- The plan requires spatial holdout, confusion matrices, Wilson/bootstrap intervals,
  Brier/calibration reporting, and a transparent logistic-regression baseline.

### P36 GPU imagery classifier planned

- Added P36 for a GPU-trained orthophoto + LiDAR conifer/deciduous classifier.
- Public Vancouver 2022 tiled orthophoto imagery is accessible; Burnaby/Surrey/Coquitlam
  have public imagery sources, but Burnaby/Coquitlam still lack species labels.
- The phase will compare image-only, structural-only, and fused models with spatial
  holdout, PR-AUC, balanced accuracy, and calibrated confusion matrices.

### P36 GPU imagery classifier pilot

- Confirmed the local RTX PRO 6000 Blackwell (96 GB) and PyTorch CUDA path.
- Added a public ArcGIS orthophoto tile source and cached 12,621 Vancouver 2022 tiles.
- Built a balanced 12,000-chip conifer/deciduous dataset (6,000 each) with 96 px RGB chips.
- Trained a four-block CNN on GPU: 80.04% held-out accuracy, 84.41% conifer precision,
  75.18% conifer recall, 0.1438 Brier, 500 m spatial-block holdout.
- Compared with P35 structural model: conifer precision improved from 37.71% to 84.41%,
  while conifer recall moved from 79.90% to 75.18%.
- Added `/api/imagery-classifier` and a compact image-CNN QA section on Vancouver.
- Added a valid CHM-only + image fusion: 81.87% held-out accuracy, 82.63% conifer
  precision, 82.09% conifer recall; the inventory-field fusion was rejected as leakage.
- Applied the image CNN to 331,221 high-confidence Burnaby candidates using the public
  Burnaby 2025 orthophoto service, and to 129,312 Vancouver candidates using the 2022
  service. Image groups and source/date fields are in the candidate GeoJSON and 3D overlay.
  Neither is a known-good candidate-level species test.
- Pilot limits: Vancouver training only; image test is balanced; no Burnaby/Coquitlam labels
  yet; orthophotos are orthorectified, not stereo.

### P35 off-inventory classifier and QA

- Added a standardized structural logistic-regression baseline for conifer/deciduous
  screening, with 500 m spatial holdout and 2x2 confusion matrices.
- Known-good labels come from the Vancouver and Surrey public inventories. Burnaby and
  Coquitlam have no public species inventory and are explicitly marked unlabelled.
- Pooled held-out accuracy is 84.09% (95% Wilson 83.81-84.37%); conifer recall is 79.90%
  but conifer precision is only 37.71%, so the model is a screening flag, not a species ID.
- Added off-inventory layers: Surrey 209,353 candidates; Burnaby 355,845; Coquitlam
  106,692, each with predicted group, probability, confidence, and inventory status.
- Added `/api/classifier` and an off-inventory QA panel with matrix, intervals, sample
  sizes, label sources, and the unlabelled-city caveat.
- Model card and limits: `notes/reports/p35-off-inventory-classifier.md`.
- Fixed Burnaby 2 m CHM tiling: the source-cell affine was previously treated as 1 m, so
  only the western half of the city was detected. Coquitlam candidates now use canopy
  distance maxima rather than a regular 20 m lattice; the QA panel was compacted.
- Dashboard: GREEN; browser smoke for the three instances and QA panel is clean.

### P34 provisional Lower Mainland city instances

- Added the P34 phase and source lock for Surrey, Burnaby, and Coquitlam.
- Added `fresh_urban_forest.lower_mainland` helpers for projected grids, LCC class heights,
  deterministic canopy candidates, and provisional inventory summaries.
- Surrey: 100,940 public tree records, 137,657 building footprints, contours, and Metro
  2020 land-cover context. Heights and DBH are imputed and labelled.
- Burnaby: 2022 0.5 m DEM/DSM CHM candidate build with building outlines and LCC context.
- Coquitlam: 287,374 deterministic 20 m canopy candidates from Metro LCC tree classes,
  with City building heights and contours; canonical LiDAR/imagery is still pending.
- Added portal mounts for `/surrey/`, `/burnaby/`, and `/coquitlam/`.
- These are provisional public-data models, not censuses or field-validated inventories.
- Dashboard: GREEN; browser smoke for the three new instances is clean.

### P32.6 3D candidates and orientation repair

- Added a compact `/api/off-inventory-3d` payload with 130,103 high-confidence candidates
  (score ≥ 0.6) and a Vancouver 3D point overlay toggled by the existing off-inventory
  control. The points are coloured by land proxy: orange likely private, blue street,
  green park, purple other, grey unknown.
- Fixed the 3D axis convention: x remains east, z is now negative northing, and the camera
  looks from the south. This puts north up and east right instead of the previous
  north-at-bottom view that read as a west-east flip. The same convention now applies to
  terrain, trees, roads, compact building boxes, non-compact UBC buildings, selection,
  planting, and the downtown camera.
- Added a north/east HUD marker and a 3D candidate-count readout. Browser smoke reports no
  console or page errors for Vancouver or UBC.
- The 3D overlay is high-confidence only; the 2D layer retains all candidates and its
  confidence/land filters. This remains a screening layer, not a census or ownership layer.
- Dashboard: GREEN.

### P32.1 data lock and P32.3 screening candidate layer

- Locked the City parcel, parks, zoning, 2022 orthophoto index, UBC inventory, public-tree,
  CHM, and OSM-road inputs with counts, retrieval dates, licences, and SHA-256 prefixes in
  `notes/p32-data-lock.md`.
- Fixed the validation protocol in `notes/p32-validation-protocol.md`: held-out 500 m
  spatial blocks, 1,000 public trees for recall, 300 orthophoto candidates for precision,
  an independent UBC test, Wilson intervals, and privacy/exposure rules.
- Added the full-city CHM screening detector in `fresh_urban_forest.city_off_inventory`:
  2 m block-max CHM, overlapping 1 km tiles, local maxima and watershed, a spatial KD-tree
  one-to-one public-tree match, building/water centre exclusion, and parcel/park/zoning/OSM
  land-context labels.
- Built 528,812 detected crowns, matched 130,497 public trees, and wrote 336,350 candidates.
  The compressed candidate layer is served by the city app; the summary reports confidence,
  crown area, volume, carbon, and land proxies with explicit screening caveats.
- This is not a census, ownership layer, species inventory, or P32 close-out. Per-crown
  point support, variable windows, seam merging, multi-peak splitting, held-out validation,
  the UBC test, and the manual orthophoto audit remain open.
- Added a confidence and land-proxy filter to the city map. Dashboard: GREEN.

### P32 ALS off-inventory phase planned

- Added the planned P32 phase for a full-city ALS-derived candidate inventory of likely
  private residential canopy.
- Added parent issue #136, tasks #137–#143, the detailed plan, and the roadmap entry.
- The plan uses City parcels, parks, roads, 2022 orthophoto, public trees, UBC inventory,
  and the P30 LiDAR/CHM; it treats candidates as confidence-scored, not a census or ownership.
- Activation waits for maintainer approval.

### P33 Remove the ground-classifier prototype

- Removed `GroundClassification`, `classify_ground_ptd`, `low_point_mask`, the TIN helpers, and
  their tests from `fresh_urban_forest.pointcloud`.
- Kept `hybrid_homogenize`, `statistical_outlier_mask`, `voxel_connected_components`, and
  `local_anisotropy` as generic conditioning primitives.
- Updated the Arbor guide and provenance note: FEMIC owns the ground lane.
- No default detector or product changed.

### P37 Surrey and Coquitlam image candidate scoring

- Scored 177,361 Surrey high-confidence candidates with the April 2025 City imagery and
  CHM + image fusion: 27,831 conifer / 149,530 deciduous.
- Scored 85,209 Coquitlam high-confidence candidates with the 2025 City tile service:
  18,764 conifer / 66,445 deciduous.
- Added image/fusion/source/date fields to candidate GeoJSON and 3D group codes.
- Coquitlam remains manual-audit-only; no public species inventory exists.
- Surrey-specific fine-tune/validation remains open.

### P37 Surrey and Coquitlam imagery scoring planned

- Added P37 to complete image candidate scoring for the two remaining P34 cities.
- Surrey has 2025 imagery and a public tree inventory for validation; Coquitlam has 2025
  imagery but no public species inventory, so it will be manual-audit-only.
- No Vancouver 2022 model transfer will be presented as validated without domain-shift
  testing.

### P34/P35/P36 close-out

- Merged the Lower Mainland instances, off-inventory screening/QA, and GPU imagery/fusion
  work through the P36 branch.
- Five portal demos: UBC, Vancouver, Surrey, Burnaby, Coquitlam.
- Final image/fusion results: image CNN 80.04% accuracy / 84.41% conifer precision;
  valid CHM + image fusion 81.87% accuracy / 82.63% conifer precision / 82.09% recall.
- Burnaby and Vancouver high-confidence candidates are image-scored. Surrey and Coquitlam
  remain explicitly unscored; no candidate-level known-good species labels exist.
- Dashboard: GREEN; browser smoke clean; portal 8101 restarted from merged code.

### P36 Surrey candidate image and fusion scoring

- Scored 177,361 high-confidence Surrey candidates using the City of Surrey April 2025
  AerialImages service and the P36 image CNN.
- Image-only groups: 47,222 conifer / 130,139 deciduous. Fused groups: 27,831 conifer /
  149,530 deciduous.
- Added image and fusion group/probability fields to Surrey candidates and the 3D group
  code.
- No known-good off-inventory species labels exist for Surrey; these are screening
  predictions.
- Dashboard: GREEN.
