# FRESH Urban Forest Lab Roadmap

This roadmap is the plan of record and the issue tracker map for FRESH Urban Forest Lab. It is kept in step with the GitHub issues, `CHANGE_LOG.md`, and `notes/`. `scripts/check_workflow.py` parses the phase headers, status lines, and checkboxes below, so keep their format.

## Issue Tracker Map

| Phase | Parent issue | Branch | Status |
| --- | --- | --- | --- |
| P0 Bootstrap and data reconnaissance | #1 | `feature/p0-p4-prototype` | complete |
| P1 Canonical urban-forest dataset | #2 | `feature/p0-p4-prototype` | complete |
| P2 Tree-level analytics and growth | #3 | `feature/p0-p4-prototype` | complete |
| P3 2D and 3D decision-support prototype | #4 | `feature/p0-p4-prototype` | complete |
| P4 Verify and demo | #5 | `feature/p0-p4-prototype` | complete |
| P5 Release and public deployment | #6 | `feature/p5-release` | planned |
| P6 Operate and maintain | #7 | `feature/p6-operate` | planned |
| P7 Solar shade and species-fit engine | #40 | `feature/p7-shade-species` | complete |
| P8 Spatio-temporal optimization and Pareto explorer | #41 | `feature/p8-optimize-pareto` | active |
| P9 Off-inventory and private-canopy augmentation | #42 | `feature/p9-off-inventory` | planned |
| P10 Bird habitat and demography | #43 | `feature/p10-birds` | planned |
| P11 Integration and v0.3 release candidate | #44 | `feature/p11-integration` | planned |

## Lifecycle Map

| Stage | Phases | Exit criteria |
| --- | --- | --- |
| Scope and design | P0, P7.1 | Sources, licences, architecture, evidence review, and ADRs recorded |
| Build | P1, P2, P3, P7, P8, P9, P10 | A dataset, a growth/DSS core, a working 2D/3D app, and the shade/optimization/canopy/bird layers |
| Verify | P4, P11 | Dashboard green, real data built, browser checked, method notes written, benchmark reproduced |
| Release and deploy | P5, P11.4 | Tag, release notes, Pages, clean-clone verification |
| Operate and maintain | P6 | Review cadence, source triage, contract migration policy |

## Conventions

- A phase is `P<n>`. A task is `P<n>.<m>`. A subtask is a checklist item inside the task's issue body. Three levels at most.
- Status values are `planned`, `active`, `pr-open`, `complete`, and `deferred`.
- A phase becomes `complete` only after its work is on `main` and its parent issue closes.
- Data and method claims must name their source and their uncertainty. See `AGENTS.md`.

## Phase 0: Bootstrap and data reconnaissance

Parent issue: #1
Branch: `feature/p0-p4-prototype`
Status: complete

Goal: seed the repository from the UBC-FRESH dev workflow, confirm the public data sources, and record the architecture and licences before writing domain code.

- [x] P0.1 Adapt the workflow contract, README, licence, citation, and CI (#8)
  - [x] Seed the project from `ubc-fresh-dev-workflow`
  - [x] Add MIT, citation, code of conduct, and data-licence files
  - [x] Adapt the package, CI, and dashboard to the new dependency set
- [x] P0.2 Data-source reconnaissance and licence review (#9)
  - [x] Catalog UBC tree, building, boundary, and LiDAR products
  - [x] Catalog City of Vancouver trees and three LiDAR dates
  - [x] Record Metro Vancouver 2022 and the caveats for change analysis
- [x] P0.3 Architecture and ADRs (#10)
  - [x] `notes/design/architecture.md`
  - [x] ADRs 0001 to 0004
  - [x] Software-landscape note with licence decisions
- [x] P0.4 Canonical data contracts and package skeleton (#11)
  - [x] Frozen dataclasses for tree, terrain, manifest, edit, scenario, and result
  - [x] JSON round-trip helpers and typed module layout
  - [x] CLI skeleton and FastAPI app factory
- [x] P0.5 Green dashboard and CI adapt to the package and web extras (#12)
  - [x] `pyproject.toml` owns the package, tools, and coverage source
  - [x] CI installs the package with dev and web extras
  - [x] Dashboard, validator, and docs build pass

Acceptance criteria:

- The dashboard is green on the seed and after the domain code is added.
- The data-source and software-landscape notes exist with licences and caveats.
- ADRs 0001 to 0004 are accepted.

Phase 0 verification:

- `python scripts/dashboard.py`
- `python scripts/check_workflow.py`

## Phase 1: Canonical urban-forest dataset

Parent issue: #2
Branch: `feature/p0-p4-prototype`
Status: complete

Goal: turn public tree inventory and LiDAR products into a portable, provenance-rich dataset.

- [x] P1.1 Dataset catalog and resumable, hashed materialization (#13)
  - [x] YAML source registry with licence, CRS, and products
  - [x] Range-resume download with `.part` atomic rename
  - [x] SHA-256 and materialization manifest
- [x] P1.2 UBC tree inventory adapter and normalisation (#14)
  - [x] GeoJSON and CSV readers
  - [x] Field mapping, species grouping, native flag, and status
  - [x] Bounding-box filter
- [x] P1.3 Vancouver public-tree adapter (#15)
  - [x] CSV reader with geometry fallback
  - [x] Shared `TreeRecord` output
- [x] P1.4 LiDAR CHM, DEM, DSM, and LAZ ingestion (#16)
  - [x] Raster reader with nodata masking
  - [x] DSM minus DEM CHM, with edge-grid trimming
  - [x] Point-cloud summary and highest-return CHM
- [x] P1.5 Terrain and canopy metrics (#17)
  - [x] DEM/CHM sampling at tree locations
  - [x] Cover, volume, height percentiles, and slope
  - [x] Terrain grid downsampling for the browser
- [x] P1.6 Canonical dataset writer and demo bundle (#18)
  - [x] `manifest.json`, trees, metrics, terrain, buildings, boundary
  - [x] Round-trip loader and summary
  - [x] Derived UBC core-campus demo
- [x] P1.7 LidarBC and CanElevation tile discovery (#38)
  - [x] Normalised tile record and JSON manifest
  - [x] LidarBC ArcGIS index by WGS84 bbox and layer
  - [x] CanElevation GeoPackage index by bbox, provider, and project
  - [x] CLI discovery, index download, and tile fetch
  - [x] UBC pilot discovery check and one-tile download/QA

Acceptance criteria:

- `fresh-urban-forest build` writes the documented dataset files.
- The demo dataset loads and reports its source lineage.
- Raster and tree metrics are calculated in a projected CRS.

Phase 1 verification:

- `fresh-urban-forest info --dataset data/demo/ubc_core`
- `python -m pytest tests/test_spatial.py tests/test_catalog_materialize.py`

## Phase 2: Tree-level analytics and growth

Parent issue: #3
Branch: `feature/p0-p4-prototype`
Status: complete

Goal: add transparent tree-level growth, canopy structure, carbon, individual-tree detection, repeat-measures change, and scenario decision support.

- [x] P2.1 Allometric growth model with crown-light-exposure adjustment (#19)
  - [x] Species groups and group profiles
  - [x] Height, DBH, crown width, and crown volume
  - [x] Annual increment and one-year growth
- [x] P2.2 Canopy volume, species, size-class, and native-share metrics (#20)
  - [x] Composition and Shannon diversity
  - [x] Size-class distribution
  - [x] Cover and volume reconciliation with the raster baseline
- [x] P2.3 Above-ground carbon and ecosystem-indicator exports (#21)
  - [x] Jenkins biomass and carbon
  - [x] Scenario CSV and GeoJSON exports
- [x] P2.4 Scenario engine for plant, remove, replace, and move (#22)
  - [x] Typed append-only edits
  - [x] Annual projection with metrics per year
  - [x] Cost and DSS score
- [x] P2.5 DSS scoring and explainable planting recommendations (#23)
  - [x] Open, low-canopy, near-tree, non-building candidate filter
  - [x] Slope and boundary constraints
  - [x] Candidate reasons and plant edits
- [x] P2.6 CHM individual-tree detection and repeat-measures change (#24)
  - [x] Local maxima plus marker-controlled watershed
  - [x] Crown radius, area, and GeoJSON export
  - [x] Gain, loss, stable canopy, and height-change summary

Acceptance criteria:

- A scenario projects year by year and exports CSV and GeoJSON.
- Recommendations carry their reasons.
- The method note states what is measured and what is estimated.

Phase 2 verification:

- `python -m pytest tests/test_allometry.py tests/test_growth_dss.py tests/test_spatial.py`
- `fresh-urban-forest detect-trees --dataset data/demo/ubc_core --out tmp/detected.geojson`

## Phase 3: 2D and 3D decision-support prototype

Parent issue: #4
Branch: `feature/p0-p4-prototype`
Status: complete

Goal: deliver a working local web application with a 2D map, a 3D terrain and instanced-tree scene, editable scenarios, and a planting advisor.

- [x] P3.1 FastAPI service and scenario persistence (#25)
  - [x] Dataset, tree, scene, image, and metrics endpoints
  - [x] Scenario create, patch, project, compare, and export
  - [x] Atomic scenario JSON with revision checks
- [x] P3.2 MapLibre 2D canopy, buildings, boundary, and tree layers (#26)
  - [x] Local hillshade and canopy PNG overlays
  - [x] Selected-tree highlight and click inspector
  - [x] Layer toggles
- [x] P3.3 Three.js terrain mesh and instanced vector trees (#27)
  - [x] Heightfield terrain with vertex colours
  - [x] Instanced trunks and crowns by species group
  - [x] Orbit controls and raycast selection
- [x] P3.4 Shared 2D/3D selection and planting/move interactions (#28)
  - [x] Shared selected tree id and inspector
  - [x] Plant and move modes on both views
  - [x] 3D click to lon/lat conversion
- [x] P3.5 Scenario dashboard, charts, comparison, and exports (#29)
  - [x] KPI strip and delta strip
  - [x] Canopy timeline, composition, and size charts
  - [x] Scenario comparison cards and downloads
- [x] P3.6 Offline vendored assets and CLI serve command (#30)
  - [x] Vendored MapLibre and Three.js
  - [x] Loopback-only default and `--allow-remote`
  - [x] Demo dataset in `data/demo/ubc_core`
- [x] P3.7 Local LLM assistant and 3D building context (#37)
  - [x] `/api/agent` and `/api/agent/chat` with a sanitized subprocess environment
  - [x] `+ Ask` pill, pop-up chat panel, quick prompts, markdown, and tool-action chips
  - [x] Browser context for the dataset, selected tree, scenario, metrics, and view
  - [x] Terrain-based building base elevation and extruded 3D footprints

Acceptance criteria:

- `fresh-urban-forest serve --dataset data/demo/ubc_core` loads in a browser.
- The map and 3D scene select the same tree record.
- A preview creates, projects, and compares a scenario.

Phase 3 verification:

- `fresh-urban-forest serve --dataset data/demo/ubc_core --port 8000`
- `python -m pytest tests/test_service.py tests/test_web_assets.py`

## Phase 4: Verify and demo

Parent issue: #5
Branch: `feature/p0-p4-prototype`
Status: complete

Goal: prove the prototype on a real UBC dataset and record the evidence.

- [x] P4.1 Unit, contract, spatial, CLI, and service tests (#31)
  - [x] 190 tests across the layers
  - [x] Coverage gate at 85 percent branch coverage
  - [x] CLI subprocess-style tests through Typer
- [x] P4.2 Browser smoke check and screenshots (#32)
  - [x] Chromium check of the 2D map and 3D scene
  - [x] No console errors in the final check
  - [x] Screenshots retained locally for review
- [x] P4.3 Real-data verification report (#33)
  - [x] UBC 2021 CHM/DEM and tree inventory built
  - [x] 9,259 live tree metrics and 66.6 percent raster cover
  - [x] LAZ point-cloud summary
- [x] P4.4 Documentation, llms.txt, and method notes (#34)
  - [x] Quick start, data, contracts, methods, and software landscape
  - [x] Agent session protocol
  - [x] API reference for the package
- [x] P4.5 Close-out package (#35)
  - [x] Close-out report in `notes/reports/p4-closeout.md`
  - [x] Parent issues closed with evidence
  - [x] Next actions queued for P5

Acceptance criteria:

- The green dashboard is green.
- A real UBC 2021 dataset builds and serves.
- The browser shows the 2D map and 3D scene without console errors.

Phase 4 verification:

- `python scripts/dashboard.py`
- `fresh-urban-forest info --dataset data/demo/ubc_core`
- `python -m pytest`

## Phase 5: Release and public deployment

Parent issue: #6
Branch: `feature/p5-release`
Status: planned

Goal: tag a public release, publish the docs site, and verify the demo from a clean clone. Before tagging, complete the observed-change, completeness, and validation plan in `notes/design/change-uncertainty-plan.md`.

- [ ] P5.0 Observed change, inventory completeness, detection validation, and local calibration (#39)
- [ ] P5.1 Release notes and known-gaps list
- [x] P5.2 Pages and live-demo check
- [ ] P5.3 Tag and GitHub release (maintainer approval required)

Acceptance criteria:

- A clean clone installs and runs the demo.
- The docs site builds from the tagged commit.
- The release names its limitations and data licences.

## Phase 6: Operate and maintain

Parent issue: #7
Branch: `feature/p6-operate`
Status: planned

Goal: keep the catalog current, triage new datasets and methods, and review the prototype on a cadence.

- [ ] P6.1 Incoming-source and method triage rule
- [ ] P6.2 Quarterly review checklist, exercised once
- [ ] P6.3 Versioning and migration policy for the dataset contract

Acceptance criteria:

- The review is held and recorded.
- New sources are accepted or rejected against a written rule.
- A schema change has a migration note.

## Phase 7: Solar shade and species-fit engine

Parent issue: #40
Branch: `feature/p7-shade-species`
Status: complete

Goal: model daily, seasonal, and annual solar exposure with terrain, buildings, and trees, then turn that into tree-level marginal shade, species fit, growth, vigour, drought stress, and irrigation cost.

Plan: `notes/design/urban-canopy-program-plan.md`.
Evidence: `notes/reference/literature-review-shade-optimization-biodiversity.md`.

- [x] P7.1 Evidence review and method lock (#45)
- [x] P7.2 Solar geometry and shadow kernel (#46)
- [x] P7.3 Shade accounting and marginal contribution (#47)
- [x] P7.4 Species traits and site fit (#48)
- [x] P7.5 Coupled light-water-growth-vigour model (#49)
- [x] P7.6 Irrigation policy and cost (#50)
- [x] P7.7 Shade and species UI (#51)
- [x] P7.8 Validation, uncertainty, and report (#52)

Acceptance criteria:

- A date/time request returns a georeferenced shadow raster and shade metrics.
- A full-year aggregate returns seasonal and annual shade-hours with uncertainty.
- A tree shade card separates building shade, canopy shade, and marginal tree shade.
- A species list is ranked by site fit with limiting factors and evidence tiers.
- A water/irrigation card gives stress days and a cost range.
- The dashboard is green and the docs describe the method and limits.

Phase 7 verification:

- `python scripts/dashboard.py`
- `fresh-urban-forest shade --dataset data/demo/ubc_core --date 2026-06-21 --times 08:00,12:00,16:00 --out tmp/shade`
- `fresh-urban-forest species-fit --dataset data/demo/ubc_core --species "Acer rubrum" --out tmp/fit.json`

## Phase 8: Spatio-temporal optimization and Pareto explorer

Parent issue: #41
Branch: `feature/p8-optimize-pareto`
Status: active

Goal: solve many spatio-temporal planting, removal, species, and irrigation problems, compile a fuzzy Pareto archive, and explore the high-dimensional tradeoff space as an interactive 3D solution cloud.

Plan: `notes/design/urban-canopy-program-plan.md`.

- [ ] P8.1 Decision model and objective schema
- [ ] P8.2 Fast evaluator and surrogate
- [ ] P8.3 Parallel solver and job orchestration
- [ ] P8.4 Pareto archive and fuzzy dominance
- [ ] P8.5 3D solution-space explorer
- [ ] P8.6 Benchmark, sensitivity, and report

Acceptance criteria:

- A 100-site, 5-species, 20-year problem with at least four objectives solves end to end.
- The archive is non-dominated, reproducible from a seed, and carries uncertainty.
- The UI can orbit, slice, brush, and load a solution as a scenario.
- The benchmark reports hypervolume, runtime, and surrogate error.
- The dashboard is green.

Phase 8 verification:

- `python scripts/dashboard.py`
- `fresh-urban-forest optimize --problem data/demo/ubc_core/optimization_example.json --workers 8 --out tmp/optimize`
- `fresh-urban-forest pareto --archive tmp/optimize/archive.json --slices 3 --out tmp/pareto`

## Phase 9: Off-inventory and private-canopy augmentation

Parent issue: #42
Branch: `feature/p9-off-inventory`
Status: planned

Goal: detect and reconcile trees missing from the official inventory, estimate the value of including them, and keep private-property data safe.

Plan: `notes/design/urban-canopy-program-plan.md`.
Evidence: `notes/reference/literature-review-shade-optimization-biodiversity.md`.

- [ ] P9.1 Terminology, privacy, and data governance
- [ ] P9.2 Land mask and ownership proxy
- [ ] P9.3 Off-inventory detection and attribution
- [ ] P9.4 Inventory reconciliation and update workflow
- [ ] P9.5 Value-of-information experiment
- [ ] P9.6 UI, confidence layer, and report

Acceptance criteria:

- An off-inventory layer exists for the pilot with confidence and land class.
- Reconciliation separates unmatched, missed, and false-positive cases.
- A value-of-information experiment reports whether the plan changes.
- No private owner data is tracked or exposed.
- The dashboard is green.

Phase 9 verification:

- `python scripts/dashboard.py`
- `fresh-urban-forest off-inventory --dataset data/processed/ubc_lidar_2021 --parcels data/raw/parcels --out tmp/off_inventory`

## Phase 10: Bird habitat and demography

Parent issue: #43
Branch: `feature/p10-birds`
Status: planned

Goal: connect 3D canopy structure and management scenarios to bird habitat, relative abundance, and a prior-driven demographic projection with explicit uncertainty.

Plan: `notes/design/urban-canopy-program-plan.md`.
Evidence: `notes/reference/literature-review-shade-optimization-biodiversity.md`.

- [ ] P10.1 Bird data and evidence tier
- [ ] P10.2 3D habitat metrics
- [ ] P10.3 Habitat and relative-abundance model
- [ ] P10.4 Demographic layer and lambda
- [ ] P10.5 Scenario UI and reporting
- [ ] P10.6 Validation and expert review

Acceptance criteria:

- A scenario returns habitat metrics and relative abundance with uncertainty.
- A demographic projection returns survival curves and lambda with intervals.
- The UI labels the evidence tier and does not imply site-specific survival.
- An expert review is recorded.
- The dashboard is green.

Phase 10 verification:

- `python scripts/dashboard.py`
- `fresh-urban-forest birds --dataset data/demo/ubc_core --observations data/raw/ebird.csv --out tmp/birds`

## Phase 11: Integration and v0.3 release candidate

Parent issue: #44
Branch: `feature/p11-integration`
Status: planned

Goal: make the shade, species, optimization, off-inventory, and bird layers one coherent lab, document them, benchmark them, and queue a v0.3 release candidate.

Plan: `notes/design/urban-canopy-program-plan.md`.

- [ ] P11.1 Unified scenario and evidence contract
- [ ] P11.2 Integrated UI and exports
- [ ] P11.3 Benchmark, reproducibility, and docs
- [ ] P11.4 v0.3 release candidate

Acceptance criteria:

- A user can run a scenario and see shade, water, cost, birds, and a Pareto archive.
- A clean clone reproduces the benchmark from a manifest.
- The docs describe every method and limit.
- The release candidate is queued; no tag exists without approval.

Phase 11 verification:

- `python scripts/dashboard.py`
- `python scripts/check_workflow.py`
- `fresh-urban-forest serve --dataset data/demo/ubc_core --port 8000`

## Detailed Next Steps Notes

1. The repository was created from `UBC-FRESH/ubc-fresh-dev-workflow` on 2026-11-03. The seed's dashboard, validator, docs, and agent contract are retained.
2. UBC 2021 LiDAR and the UBC tree inventory were built into a local processed dataset and a smaller tracked demo. The full raw and processed rasters stay out of git; the demo manifest records lineage.
3. The core is standalone by design (ADR 0002). `fresh-fvsbc` remains an optional future adapter for calibrated growth, not a core import.
4. The software landscape note records why OpenTreeMap (AGPL) and ForestTools/lidR/PyCrown/itcSegment (GPL) are method references only. The repository is MIT.
5. Phase 5 is planned. It needs maintainer approval before a tag, release, Pages setting change, or live deployment.
6. Phase 6 is planned. The first review should decide whether to add a planting-site entity, a work-order log, and a fitted local growth model.
7. Phases 0 to 4 merged as PR #36 (`1e0a9b0`). The parent issues #1 to #5 and their child issues #8 to #35 are closed. Subsequent hygiene commits on `main` fixed the editable-install ignore, the documentation package install, and the Pages deferral. CI and the Docs workflow are green on `main` as of `dc9f599`.
8. P3.7 (#37) added the local OpenCode assistant and fixed 3D buildings by sampling terrain elevation at each footprint centroid and extruding the footprint geometry. The assistant is opt-in with `--allow-agent` and runs the local `opencode` CLI with a sanitized environment. The reverse-proxy path-prefix fix is also on `main`.
9. P1.7 (#38) added external tile discovery. The UBC pilot bbox returned 34 LidarBC point-cloud tiles and 15 CanElevation tiles. The CanElevation 2016 Lower Mainland tiles duplicate the LidarBC 2016 coverage, so they are a COPC/cloud-optimised alternative rather than an independent repeat measure. One 6.04 MB LidarBC tile was downloaded and summarised as a QA check.
10. The P7-P11 programme is queued as planned phases (#40-#44) with the detailed plan in `notes/design/urban-canopy-program-plan.md` and the rapid evidence review in `notes/reference/literature-review-shade-optimization-biodiversity.md`. The recommended order is P7 shade/species, P8 optimization/Pareto, P9 off-inventory, P10 birds, P11 integration. No phase is active.
11. The P7-P11 queue does not block the v0.2.0 release candidate. P5 remains the release gate; its tag, release, and settings actions still need explicit maintainer approval.
