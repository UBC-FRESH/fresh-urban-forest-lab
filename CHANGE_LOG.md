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
