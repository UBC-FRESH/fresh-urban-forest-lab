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
| P5 Release and public deployment | #6 | `release/v0.3.0` | complete |
| P7 Solar shade and species-fit engine | #40 | `feature/p7-shade-species` | complete |
| P8 Spatio-temporal optimization and Pareto explorer | #41 | `feature/p8-optimize-pareto` | complete |
| P9 Off-inventory and private-canopy augmentation | #42 | `feature/p9-off-inventory` | complete |
| P10 Bird habitat and demography | #43 | `feature/p10-birds` | complete |
| P11 Integration and v0.3.0 release | #44 | `feature/p11-integration` | complete |
| P12 Arbor method mining and clean-room point-cloud primitives | #61 | `feature/p12-arbor-methods` | complete |
| P13 ALS ground classification and height above ground | #70 | `feature/p13-als-ground` | complete |
| P14 Ground reference and second terrain validation | #89 | `feature/p14-ground-reference` | complete |
| P15 Manual ground reference and optional FEMIC adapter design | #95 | `feature/p15-ground-adapter` | complete |
| P16 Optional FEMIC ground-adapter implementation | #103 | `feature/p16-ground-adapter` | complete |
| P17 CHM/ITD post-processing | #113 | `feature/p17-itd-postprocess` | complete |
| P18 CHM/ITD post-processing exports and smoke test | #116 | `feature/p18-itd-exports` | complete |
| P19 Merge-reduction audit and guard | #119 | `feature/p19-merge-audit` | complete |
| P20 Non-transitive crown merge and manual audit patch | #122 | `feature/p20-anchor-merge` | complete |
| P21 Ground-adapter second-tile smoke test | #126 | `feature/p21-ground-smoke` | complete |
| P30 Full Vancouver city canopy and ecosystem-services pilot | #105 | `feature/p30-vancouver-city` | complete |
| P31 Move the ground writer to FEMIC | #135 | `feature/p31-move-ground-writer` | complete |
| P32 ALS-derived off-inventory and private-canopy inventory | #136 | `feature/p32-off-inventory-als` | active |
| P33 Remove the ground-classifier prototype | #146 | `feature/p33-remove-ground-classifier` | complete |
| P34 Surrey, Burnaby, and Coquitlam portal instances | #149 | `feature/p34-lower-mainland-instances` | active |
| P35 Off-inventory conifer/deciduous classifier and QA | #156 | `feature/p35-off-inventory-classifier` | active |
| P36 GPU imagery-enhanced conifer/deciduous classifier | #161 | `feature/p36-imagery-classifier` | active |

## Lifecycle Map

| Stage | Phases | Exit criteria |
| --- | --- | --- |
| Scope and design | P0, P7.1 | Sources, licences, architecture, evidence review, and ADRs recorded |
| Build | P1, P2, P3, P7, P8, P9, P10, P30 | A dataset, a growth/DSS core, a working 2D/3D app, and the shade/optimization/canopy/bird layers |
| Verify | P4, P11, P30 | Dashboard green, real data built, browser checked, method notes written, benchmark reproduced |
| Release and deploy | P5, P11.4 | Tag, release notes, Pages, clean-clone verification |

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
Branch: `release/v0.3.0`
Status: complete

Goal: tag v0.3.0, publish the docs site, and verify the demo from a clean clone.

- [x] P5.0 Observed change, inventory completeness, detection validation, and local calibration (#39)
- [x] P5.1 Release notes and known-gaps list
- [x] P5.2 Pages and live-demo check
- [x] P5.3 Tag and GitHub release v0.3.0

Acceptance criteria:

- A clean clone installs and runs the demo.
- The docs site builds from the tagged commit.
- The release names its limitations and data licences.

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
Status: complete

Goal: solve many spatio-temporal planting, removal, species, and irrigation problems, compile a fuzzy Pareto archive, and explore the high-dimensional tradeoff space as an interactive 3D solution cloud.

Plan: `notes/design/urban-canopy-program-plan.md`.

- [x] P8.1 Decision model and objective schema
- [x] P8.2 Fast evaluator and surrogate
- [x] P8.3 Parallel solver and job orchestration
- [x] P8.4 Pareto archive and fuzzy dominance
- [x] P8.5 3D solution-space explorer
- [x] P8.6 Benchmark, sensitivity, and report

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
Status: complete

Goal: detect and reconcile trees missing from the official inventory, estimate the value of including them, and keep private-property data safe.

Plan: `notes/design/urban-canopy-program-plan.md`.
Evidence: `notes/reference/literature-review-shade-optimization-biodiversity.md`.

- [x] P9.1 Terminology, privacy, and data governance
- [x] P9.2 Land mask and ownership proxy
- [x] P9.3 Off-inventory detection and attribution
- [x] P9.4 Inventory reconciliation and update workflow
- [x] P9.5 Value-of-information experiment
- [x] P9.6 UI, confidence layer, and report

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
Status: complete

Goal: connect 3D canopy structure and management scenarios to bird habitat, relative abundance, and a prior-driven demographic projection with explicit uncertainty.

Plan: `notes/design/urban-canopy-program-plan.md`.
Evidence: `notes/reference/literature-review-shade-optimization-biodiversity.md`.

- [x] P10.1 Bird data and evidence tier
- [x] P10.2 3D habitat metrics
- [x] P10.3 Habitat and relative-abundance model
- [x] P10.4 Demographic layer and lambda
- [x] P10.5 Scenario UI and reporting
- [x] P10.6 Validation and expert review

Acceptance criteria:

- A scenario returns habitat metrics and relative abundance with uncertainty.
- A demographic projection returns survival curves and lambda with intervals.
- The UI labels the evidence tier and does not imply site-specific survival.
- An expert review is recorded.
- The dashboard is green.

Phase 10 verification:

- `python scripts/dashboard.py`
- `fresh-urban-forest birds --dataset data/demo/ubc_core --observations data/raw/ebird.csv --out tmp/birds`

## Phase 11: Integration and v0.3.0 release

Parent issue: #44
Branch: `feature/p11-integration`
Status: complete

Goal: make the shade, species, optimization, off-inventory, and bird layers one coherent lab, document them, benchmark them, and release v0.3.0.

Plan: `notes/design/urban-canopy-program-plan.md`.

- [x] P11.1 Unified scenario and evidence contract
- [x] P11.2 Integrated UI and exports
- [x] P11.3 Benchmark, reproducibility, and docs
- [x] P11.4 v0.3.0 release

Acceptance criteria:

- A user can run a scenario and see shade, water, cost, birds, and a Pareto archive.
- A clean clone reproduces the benchmark from a manifest.
- The docs describe every method and limit.
- The v0.3.0 tag and GitHub release exist.

Phase 11 verification:

- `python scripts/dashboard.py`
- `python scripts/check_workflow.py`
- `fresh-urban-forest serve --dataset data/demo/ubc_core --port 8000`

## Phase 12: Arbor method mining and clean-room point-cloud primitives

Parent issue: #61
Branch: `feature/p12-arbor-methods`
Status: complete

Goal: mine the published methods and design patterns in `r-lidar/arbor` and reimplement the
low-risk point-cloud primitives in MIT-licensed Python, with explicit provenance and no
copyleft code copying.

Plan: `notes/reference/arbor-method-mining.md`.
Decision: `notes/adr/0006-clean-room-method-reuse.md`.

- [x] P12.1 Provenance scaffolding and point-cloud primitives (#62)
  - [x] Arbor source snapshot, licence posture, and candidate matrix
  - [x] ADR, software-landscape row, Sphinx page, and `llms.txt` entry
  - [x] `hybrid_homogenize`, `statistical_outlier_mask`, `voxel_connected_components`, `local_anisotropy`
  - [x] Synthetic-cloud tests and `Method provenance` docstrings

Acceptance criteria:

- The provenance note, ADR, software-landscape row, and Sphinx page exist and are linked.
- `fresh_urban_forest.pointcloud` exposes the four documented functions.
- Unit tests cover the nominal path, edge cases, and determinism.
- No Arbor source code is copied and no GPL-licensed code is added.
- The dashboard is green.

Phase 12 verification:

- `python scripts/dashboard.py`
- `python scripts/check_workflow.py`

## Phase 13: ALS ground classification and height above ground

Parent issue: #70
Branch: `feature/p13-als-ground`
Status: complete

Goal: add a PTD-inspired ground classification and height-above-ground capability for raw
LidarBC/ALS point clouds, starting in this repository and validating on a real tile before
any FEMIC integration.

Plan: `notes/reference/arbor-method-mining.md`.
Decision: `notes/adr/0006-clean-room-method-reuse.md`.

- [x] P13.1 PTD ground classification core and synthetic fixtures (#71)
  - [x] Grid-lowest seeding, progressive TIN densification, and HAG interpolation
  - [x] Typed `GroundClassification` result with seed/iteration counters and warnings
  - [x] Flat, sloped, outlier, degenerate-TIN, empty, and invalid-parameter tests
  - [x] Method provenance docstring and public docs
- [x] P13.2 Real LidarBC tile validation (#80)
  - [x] Acquired a 415,068-point LidarBC 2025 tile under OGL-BC
  - [x] Recorded class counts, class-2 recall, HAG percentiles, runtime, and caveats
  - [x] Replaced the facet-slope gate with a point-to-vertex angle gate after the first pass
- [x] P13.3 QA report and low-point-cut/SOR policy (#82)
  - [x] SOR before PTD on the 2025 and 2016 tiles
  - [x] Class-7 false-ground and class-2 recall comparison
  - [x] `low_point_mask` 0.15 m downstream policy
- [x] P13.4 FEMIC integration decision (#87)
  - [x] Deferred FEMIC integration; keep the classifier opt-in
  - [x] Recorded the reference-patch, second-terrain, and full-PTD conditions

Acceptance criteria:

- A flat plane, a sloped plane, and a scene with an above-ground outlier classify the
  expected ground points.
- HAG is near zero on synthetic ground and positive on vegetation or building outliers.
- The result records seed count, iteration count, ground count, and a warning when the TIN
  is degenerate.
- A real LidarBC tile reports ground points, HAG percentiles, and QA warnings.
- The implementation cites Axelsson (2000), Arbor book chapter 4, and Arbor's PTD note;
  no GPL code is copied.
- The dashboard is green.

Phase 13 verification:

- `python scripts/dashboard.py`
- `python scripts/check_workflow.py`

## Phase 14: Ground reference and second terrain validation

Parent issue: #89
Branch: `feature/p14-ground-reference`
Status: complete

Goal: close the P13 validation gap with a reproducible class-2 reference construction and a
second, steeper terrain tile, then revisit the FEMIC decision.

Plan: `notes/reports/p14-ground-reference.md`.

- [x] P14.1 Ground reference protocol and high-confidence negatives (#90)
  - [x] Positive = class 2; high-confidence negative = non-class-2 with reference HAG > 2 m
  - [x] Ambiguous 0-2 m band excluded; no classifier HAG used to define negatives
- [x] P14.2 Steep interior tile validation (#91)
  - [x] 2021 Golden-area tile, 113,775 points, about 62 m relief
  - [x] Class-2 recall 0.9634; high-confidence false-ground 4.65%; HAG p99 0.0441 m
- [x] P14.3 FEMIC decision revisit (#92)
  - [x] Approve an optional adapter prototype, not a default pipeline change
  - [x] Conditions recorded: manual patch, versioned adapter, stable contract

Acceptance criteria:

- The reference construction is documented and reproducible.
- The coastal and steep tiles report class-2 recall and high-confidence false-ground rate.
- The report states what the reference does and does not prove.
- The FEMIC decision is updated explicitly.
- The dashboard is green.

Phase 14 verification:

- `python scripts/dashboard.py`
- `python scripts/check_workflow.py`

## Phase 15: Manual ground reference and optional FEMIC adapter design

Parent issue: #95
Branch: `feature/p15-ground-adapter`
Status: complete

Goal: add a manually checked 20 m ground reference patch and design an optional, versioned
sidecar FEMIC adapter without changing default FEMIC products.

Plan: `notes/reports/p15-ground-reference.md`, `notes/design/femic-ground-adapter.md`.
Decision: `notes/adr/0007-optional-femic-ground-adapter.md`.

- [x] P15.1 Manually checked 20 m reference patch (#96)
  - [x] 20 m x 20 m Golden-area patch, side/top view, class 1/2/7 check
  - [x] Class-2 recall 0.9507; high-confidence false-ground 3.14%; HAG p99 0.0434 m
- [x] P15.2 Optional FEMIC adapter design (#97)
  - [x] Sidecar `ground.laz`, `manifest.json`, and `qa.json`
  - [x] Optional dependency, versioned schemas, warnings, and contract-test plan
- [x] P15.3 Decision and close-out (#98)
  - [x] Accept the design; implementation deferred to a later phase

Acceptance criteria:

- The reference patch is documented with a cross-section check and metrics.
- The FEMIC adapter design is versioned, optional, and does not change default products.
- The design names provenance, QA fields, failure modes, and test strategy.
- The classifier remains opt-in.
- The dashboard is green.

Phase 15 verification:

- `python scripts/dashboard.py`
- `python scripts/check_workflow.py`

## Phase 16: Optional FEMIC ground-adapter implementation

Parent issue: #103
Branch: `feature/p16-ground-adapter`
Status: complete

Goal: implement the optional sidecar ground-adapter designed in P15, with contract tests,
CLI, docs, and no default FEMIC product change.

Plan: `notes/design/femic-ground-adapter.md`.

- [x] P16.1 Sidecar ground-bundle writer, CLI, tests, and docs (#104)
  - [x] `GroundAdapterParameters`, `GroundAdapterParameters.sha256`, `GroundBundleResult`
  - [x] `write_ground_bundle` with extra dimensions, hashes, manifest, and QA
  - [x] `ground-adapter` CLI command
  - [x] Synthetic-LAZ contract tests and failure-mode tests
  - [x] API and public docs

Acceptance criteria:

- The writer produces `ground.laz`, `manifest.json`, and `qa.json`.
- The manifest and QA files validate their versioned schemas.
- Hashes, parameters, CRS, vertical datum, warnings, and provenance are recorded.
- The CLI is opt-in and does not change default paths.
- Contract tests cover the nominal path, missing metadata, overwrite, and empty input.
- The dashboard is green.

Phase 16 verification:

- `python scripts/dashboard.py`
- `python scripts/check_workflow.py`

## Phase 17: CHM/ITD post-processing

Parent issue: #113
Branch: `feature/p17-itd-postprocess`
Status: complete

Goal: add opt-in CHM/ITD post-processing for edge buffers, small trees, and conservative
over-segmentation merging.

- [x] P17.1 ITD post-processing module, tests, and docs (#114)
  - [x] `TreePostprocessResult` and `postprocess_trees`
  - [x] Edge buffer, small-tree flag, and conservative merge groups
  - [x] `kept()` filtering and JSON summary
  - [x] Synthetic tests and API/public docs

Acceptance criteria:

- Buffer, small-tree, and merge functions are opt-in and deterministic.
- Merge groups record every source ID and keep a stable representative ID.
- The `kept()` result excludes buffer and small-tree IDs.
- Tests cover flags, merge, no-merge, empty input, and invalid parameters.
- The dashboard is green.

Phase 17 verification:

- `python scripts/dashboard.py`
- `python scripts/check_workflow.py`

## Phase 18: CHM/ITD post-processing exports and smoke test

Parent issue: #116
Branch: `feature/p18-itd-exports`
Status: complete

Goal: expose P17 post-processing through the CLI and run it on the real UBC demo dataset.

- [x] P18.1 CLI post-processing export and smoke test (#117)
  - [x] `detect-trees --postprocess` with buffer, small-tree, and merge options
  - [x] Kept-crown GeoJSON plus sidecar summary JSON
  - [x] Default command unchanged
  - [x] Demo smoke: 859 detected, 701 kept, 57 merge groups; stress buffer flags 5

Acceptance criteria:

- `detect-trees` without the new flag behaves exactly as before.
- With the flag, it writes kept crowns and a sidecar summary.
- The summary reports buffer, small-tree, and merge counts.
- The demo run is recorded with exact counts.
- The dashboard is green.

Phase 18 verification:

- `python scripts/dashboard.py`
- `python scripts/check_workflow.py`

## Phase 19: Merge-reduction audit and guard

Parent issue: #119
Branch: `feature/p19-merge-audit`
Status: complete

Goal: audit the P17/P18 merge on the demo, fix the transitive chain collapse, and expose
merge tuning options.

- [x] P19.1 Merge audit, guard, CLI options, tests, and report (#120)
  - [x] Old rule: 57 groups, 215 crowns, largest group 67 crowns over 4.6 km
  - [x] Guarded rule: 3 local groups, 6 crowns, 859 detected -> 856 kept
  - [x] `merge_max_group_members` and `merge_max_group_extent_m`
  - [x] CLI tuning options and guard tests

Acceptance criteria:

- The audit reports the old and guarded merge-group counts and extents.
- The chain-collapse false merge is documented with evidence.
- The guarded rule prevents the chain collapse.
- The CLI exposes merge tuning options.
- Tests cover the guard behavior.
- The dashboard is green.

Phase 19 verification:

- `python scripts/dashboard.py`
- `python scripts/check_workflow.py`

## Phase 20: Non-transitive crown merge and manual audit patch

Parent issue: #122
Branch: `feature/p20-anchor-merge`
Status: complete

Goal: replace the guarded union-find merge with a non-transitive anchor merge and validate
it on a synthetic manual audit patch and the UBC demo.

- [x] P20.1 Anchor merge, synthetic audit patch, tests, and report (#123)
  - [x] Anchor pass: only larger crowns absorb; absorbed crowns cannot anchor
  - [x] Synthetic split/distinct audit patch
  - [x] Demo: 859 detected, 3 local groups, 856 kept
  - [x] Non-transitivity and multi-crown anchor tests

Acceptance criteria:

- A smaller crown cannot anchor after being absorbed.
- A large crown can absorb multiple smaller crowns within the caps.
- The synthetic patch merges the split crown and keeps distinct crowns separate.
- The demo comparison is recorded.
- The dashboard is green.

Phase 20 verification:

- `python scripts/dashboard.py`
- `python scripts/check_workflow.py`

## Phase 21: Ground-adapter second-tile smoke test

Parent issue: #126
Branch: `feature/p21-ground-smoke`
Status: complete

Goal: run the optional ground adapter on a second real LidarBC tile and compare it with the
P16 Golden-area smoke.

- [x] P21.1 Coastal-tile bundle smoke test and report (#127)
  - [x] Coastal 2025 tile: 415,068 points, 374,711 ground, 68.8 s, no warnings
  - [x] Golden 2021 tile: 113,775 points, 82,530 ground, 5.8 s, no warnings
  - [x] Both bundles use the same schemas and extra dimensions

Acceptance criteria:

- A valid bundle is written for the coastal tile.
- The manifest and QA schemas validate.
- The report records ground count, low-point count, HAG, runtime, and warnings.
- The comparison with the Golden tile is explicit.
- The dashboard is green.

Phase 21 verification:

- `python scripts/dashboard.py`
- `python scripts/check_workflow.py`


## Phase 30: Full Vancouver city canopy and ecosystem-services pilot

Parent issue: #105
Branch: `feature/p30-vancouver-city`
Status: complete

Goal: extend the UBC-core prototype to the full City of Vancouver using public data, with a
1 m city canopy surface, all 184k public trees, city and local-area metrics, and a 3D city
scene.

Plan: `notes/design/vancouver-city-pilot.md`.

- [x] P30.1 Source lock, AOI, storage budget, and full-city data manifest (#106)
- [x] P30.2 Full-city LiDAR mosaic and canopy surfaces (#107)
- [x] P30.3 Full public-tree inventory and tree-level evidence (#108)
- [x] P30.4 City-wide and local-area metrics and ecosystem services (#109)
- [x] P30.5 Vancouver 3D city scene and dashboard (#110)
- [x] P30.6 Validation, performance, docs, and close-out (#111)
- [x] P30.7 Portal landing page for the UBC and Vancouver demos (#132)

Acceptance criteria:

- The full city AOI is covered by a 1 m CHM with no unexplained gaps.
- The public-tree inventory loads at full count with measured/imputed flags.
- City and 22 local-area metrics are reproducible and carry method/evidence labels.
- The 3D Vancouver scene opens from the web app and fits the city.
- The browser smoke check and full dashboard pass.
- Docs describe every source, method, licence, and limit.
- Storage stays under a 250 GB working budget and no dataset is written outside
  `/srv/shared-data`.

Phase 30 verification:

- `python scripts/dashboard.py`
- `python scripts/check_workflow.py`
- `fresh-urban-forest serve --dataset data/processed/vancouver_2022 --port 8000`

## Phase 31: Move the ground writer to FEMIC

Parent issue: #135
Branch: `feature/p31-move-ground-writer`
Status: complete

Goal: remove the legacy ground-bundle writer and CLI from this repository and make FEMIC the
documented owner. The ground classifier prototype remains here for urban ALS experiments.

- [x] P31.1 Remove `ground_adapter`, the `ground-adapter` CLI, tests, and API entry
- [x] Update the ground-lane docs to point to FEMIC
- [x] Record the ownership move in the roadmap and changelog

Acceptance: `fresh-urban-forest ground-adapter` no longer exists; no `ground_adapter`
module remains; the docs name FEMIC as canonical; the dashboard is green.

## Phase 32: ALS-derived off-inventory and private-canopy inventory

Parent issue: #136
Branch: `feature/p32-off-inventory-als`
Status: active

Goal: turn the P9 off-inventory pilot into a full-city, confidence-scored ALS-derived
candidate inventory that can represent likely private residential canopy without claiming a
census, ownership, or species.

Plan: `notes/design/als-offinventory-inventory.md`.

- [x] P32.1 Evidence, target definition, data lock, and validation protocol (#137)
- [ ] P32.2 Full-city ALS point and CHM tile preparation (#138)
- [ ] P32.3 Individual-tree segmentation and candidate detection (#139)
- [ ] P32.4 Inventory reconciliation and public/private land proxy (#140)
- [ ] P32.5 Candidate attributes and uncertainty (#141)
- [ ] P32.6 City app off-inventory layer and private-canopy metrics (#142)
- [ ] P32.7 Validation, manual audit, docs, and close-out (#143)

Acceptance criteria:

- A full-city candidate layer, not a 500-crown pilot cap.
- Candidates are separate from the public inventory and carry confidence, height, crown,
  volume, carbon, and public/private land-proxy labels.
- No owner, address, or parcel-level ownership claim is stored or exposed.
- Detection is evaluated on held-out public trees, the UBC inventory, and a manual
  orthophoto audit; precision/recall and count uncertainty are reported.
- The city app shows the candidate layer, confidence filters, counts, and explicit caveats.
- Performance and storage are measured; no dataset is written outside `/srv/shared-data`.
- The dashboard is green.

Phase 32 verification:

- `python scripts/dashboard.py`
- `python scripts/check_workflow.py`

## Phase 33: Remove the ground-classifier prototype

Parent issue: #146
Branch: `feature/p33-remove-ground-classifier`
Status: complete

Goal: finish the ownership cleanup by removing the ground-classifier prototype that FEMIC
now owns canonically.

- [x] P33.1 Remove the PTD classifier, low-point mask, TIN helpers, and tests
- [x] Keep the generic point-cloud conditioning primitives
- [x] Update the Arbor guide and provenance note to point to FEMIC
- [x] Record the removal in the roadmap and changelog

Acceptance: no ground-classification or low-point function remains; the generic primitives
still pass their tests; Sphinx docs build without broken ground-function references; the
dashboard is green.

## Phase 34: Surrey, Burnaby, and Coquitlam portal instances

Parent issue: #149
Branch: `feature/p34-lower-mainland-instances`
Status: active

Goal: add three public-data city instances to the demo portal, with separate runtime
directories and explicit provisional-method labels.

Plan: `notes/design/lower-mainland-city-instances.md`.

- [x] P34.1 Generic city-instance pack contract and source lock (#150)
- [x] P34.2 Acquire and compile Surrey (#151)
- [x] P34.3 Acquire and compile Burnaby (#152)
- [x] P34.4 Acquire and compile Coquitlam (#153)
- [x] P34.5 Portal cards and browser verification (#154)
- [x] P34.6 Method notes, changelog, dashboard, and close-out (#155)

Acceptance criteria:

- `/surrey/`, `/burnaby/`, and `/coquitlam/` load their own datasets and runtime dirs.
- Each card labels the instance provisional/public-data and states the method.
- 2D and 3D load without console or page errors.
- No owner, address, or parcel-ownership claim is stored or displayed.
- No dataset is written outside `/srv/shared-data`.
- The dashboard is green.

Phase 34 verification:

- `python scripts/dashboard.py`
- `python scripts/check_workflow.py`

## Phase 35: Off-inventory conifer/deciduous classifier and QA

Parent issue: #156
Branch: `feature/p35-off-inventory-classifier`
Status: active

Goal: compile off-inventory layers for the three P34 instances and add a documented
conifer/deciduous classifier with confusion-matrix and confidence-interval QA.

Plan: `notes/design/off-inventory-classifier.md`.

- [x] P35.1 Labels, features, classifier, and QA metrics (#157)
- [x] P35.2 Compile off-inventory layers for three cities (#158)
- [x] P35.3 Classifier API and QA interface (#159)
- [x] P35.4 Validation, documentation, dashboard, and close-out (#160)

Acceptance:

- All three new instances expose an off-inventory candidate layer.
- Every candidate has predicted group, probability, and confidence.
- QA panel shows a confusion matrix and 95% intervals for known-good labels.
- Burnaby/Coquitlam are marked unlabelled; weak-label agreement is separate.
- Dashboard is green and browser smoke is clean.

Phase 35 verification:

- `python scripts/dashboard.py`
- `python scripts/check_workflow.py`

## Phase 36: GPU imagery-enhanced conifer/deciduous classifier

Parent issue: #161
Branch: `feature/p36-imagery-classifier`
Status: active

Goal: use the available RTX PRO 6000 and public orthophoto pixels to replace the weak
structural-only conifer/deciduous baseline with a validated imagery + LiDAR model.

Plan: `notes/design/imagery-classifier.md`.

- [x] P36.1 Orthophoto source lock and chip cache (#162)
- [x] P36.2 GPU CNN training and spatial validation (#163)
- [ ] P36.3 Fuse/compare with LiDAR structural baseline (#164)
- [ ] P36.4 Apply to off-inventory candidates and UI QA (#165)
- [ ] P36.5 Docs, dashboard, browser smoke, close-out (#166)

Phase 36 verification:

- `python scripts/dashboard.py`
- `python scripts/check_workflow.py`

## Detailed Next Steps Notes

1. The repository was created from `UBC-FRESH/ubc-fresh-dev-workflow` on 2026-11-03. The seed's dashboard, validator, docs, and agent contract are retained.
2. UBC 2021 LiDAR and the UBC tree inventory were built into a local processed dataset and a smaller tracked demo. The full raw and processed rasters stay out of git; the demo manifest records lineage.
3. The core is standalone by design (ADR 0002). `fresh-fvsbc` remains an optional future adapter for calibrated growth, not a core import.
4. The software landscape note records why OpenTreeMap (AGPL) and ForestTools/lidR/PyCrown/itcSegment (GPL) are method references only. The repository is MIT.
5. v0.3.0 is the released integrated lab. P5 is complete, the docs site is live, and the tag points to the release commit.
6. P7-P11 are complete: shade and species fit, Fresh Solutions optimization and Pareto explorer, off-inventory canopy and value of information, bird habitat and prior demography, and the unified lab report.
7. P12 (#61) mines Arbor 1.1.5 methods without copying its GPL-3.0 code. Four opt-in point-cloud primitives, the provenance note, ADR 0006, and the public docs page are complete.
8. P13 (#70) adds `classify_ground_ptd` and `GroundClassification` for the ALS ground lane. P13.4 defers FEMIC integration until a checked reference patch, a second terrain type, and a fuller PTD angle test exist.
9. P14 (#89) adds a class-2 reference surface and steep-tile validation. Class-2 recall is 0.9634 and high-confidence false-ground is 4.65% on the steep tile; the coastal tile is 0.9999 and 3.35%. An optional FEMIC adapter prototype is approved only with a manual reference patch and versioned contract.
10. P15 (#95) adds a manually checked 20 m Golden-area patch and accepts an optional sidecar FEMIC adapter design. The patch shows class-2 recall 0.9507 and high-confidence false-ground 3.14%. The adapter is not implemented; the design defines `ground.laz`, `manifest.json`, and `qa.json`, no hard FEMIC dependency, and no default product change.
11. P16 (#103) implements the optional sidecar ground adapter: `write_ground_bundle`, the `ground-adapter` CLI, extra dimensions, manifest/QA schemas, and synthetic contract tests. It remains opt-in and does not change default FEMIC products.
12. P17 (#113) adds opt-in CHM/ITD post-processing: edge buffer flags, small-tree height flags, and a conservative over-segmentation merge with source-ID groups. `kept()` excludes both flag sets; `detect_trees` defaults are unchanged.
13. P18 (#116) exposes the P17 post-processing through `detect-trees --postprocess` and writes a sidecar summary. The UBC demo detects 859 crowns, keeps 701 after 57 merge groups, and a 50 m stress buffer flags 5. The default detector path is unchanged; the merge reduction needs visual review before operational use.
14. P19 (#119) audits the demo merge and finds a transitive chain collapse: the old rule merged 67 crowns across 4.6 km. The guarded rule caps groups at 4 crowns and 30 m, reducing the demo to 3 local groups and 856 kept crowns. The guard prevents false merges but may under-merge real over-segmentation; the merge is a safety filter, not an instance solver.
15. P20 (#122) replaces the guarded union-find merge with a non-transitive anchor rule: only larger crowns absorb, and absorbed crowns cannot anchor. The synthetic audit patch merges a known split crown and keeps similar distinct crowns separate. The demo remains 3 local groups and 856 kept; a real orthophoto/field audit is still needed.
16. P21 (#126) runs the optional ground adapter on the 2025 coastal tile and compares it with the Golden 2021 tile. Coastal: 415,068 points, 374,711 predicted ground, 68.8 s. Golden: 113,775 points, 82,530 predicted ground, 5.8 s. Both bundles are schema-valid with no warnings. The low-point fraction differs because the point distributions differ.
17. P30 (#105) is the full Vancouver city pilot. It uses the City 2022 LiDAR (181 tiles, ~49 points/m²), all 184,152 public trees, the 22 local-area polygons, and building footprints. The AOI is 118.76 km² in EPSG:3157. The build produced 8.72 billion points, 99.96% LiDAR coverage, 184,151 mapped trees, 26.854% canopy cover, 350.16 million m³ canopy volume, 95,792 t above-ground carbon, and 1,979 t/yr modelled sequestration. The City's 2022 estimate is about 25%, a sanity check rather than calibration. Raw data is 165 GB under `/srv/shared-data`; processed outputs are 1.8 GB; free space remains 7.7 TB. The close-out is `notes/reports/p30-vancouver-city.md`. P30.7 adds the landing portal on port 8101 with mounted `/ubc/` and `/vancouver/` apps; the WS4 portal remains on 8790.

18. P31 (#135) moves the ground-bundle writer to FEMIC. The `ground-adapter` CLI, `ground_adapter` module, tests, and API entry are removed here; `classify_ground_ptd` remains as an urban ALS prototype. The canonical writer is `femic lidar ground-bundle-build`.
19. P32 (#136) is planned, not active. It will turn the P9 off-inventory pilot into a full-city ALS candidate inventory for likely private residential canopy, with held-out public-tree and UBC validation, an orthophoto audit, parcel/parks/street land proxies, and a city app layer. The plan is `notes/design/als-offinventory-inventory.md`; activation waits for maintainer approval.
20. P33 (#146) removes the remaining ground-classifier prototype (`classify_ground_ptd`, `GroundClassification`, `low_point_mask`, and their TIN helpers) from this repository. FEMIC is the sole owner; the generic conditioning primitives remain here.