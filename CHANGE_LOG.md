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
  objective axis labels, and a jump-back link from a `Pareto <id>` scenario to its source
  archive point.
- Fixed the 3D scene ground alignment: the terrain mesh now uses the scene origin instead
  of the grid centre, so trees and buildings are no longer shifted about 1.4 km against the
  terrain; missing DEM cells are filled from their nearest valid neighbour instead of being
  rendered as a zero-elevation hole. Building opacity is less ghostly at low camera angles.
- Tests: 285 passed. Dashboard: GREEN.
- Limits: weighted-sum finite approximation, Monte Carlo hypervolume, bootstrap robustness,
  precomputed P7 evaluator, and no city-scale claim.
