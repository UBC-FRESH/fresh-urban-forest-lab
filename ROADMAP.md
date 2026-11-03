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

## Lifecycle Map

| Stage | Phases | Exit criteria |
| --- | --- | --- |
| Scope and design | P0 | Sources, licences, architecture, and ADRs recorded |
| Build | P1, P2, P3 | A dataset, a growth/DSS core, and a working 2D/3D app |
| Verify | P4 | Dashboard green, real data built, browser checked, method notes written |
| Release and deploy | P5 | Tag, release notes, Pages, clean-clone verification |
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

Goal: tag a public release, publish the docs site, and verify the demo from a clean clone.

- [ ] P5.1 Release notes and known-gaps list
- [ ] P5.2 Pages and live-demo check
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

## Detailed Next Steps Notes

1. The repository was created from `UBC-FRESH/ubc-fresh-dev-workflow` on 2026-11-03. The seed's dashboard, validator, docs, and agent contract are retained.
2. UBC 2021 LiDAR and the UBC tree inventory were built into a local processed dataset and a smaller tracked demo. The full raw and processed rasters stay out of git; the demo manifest records lineage.
3. The core is standalone by design (ADR 0002). `fresh-fvsbc` remains an optional future adapter for calibrated growth, not a core import.
4. The software landscape note records why OpenTreeMap (AGPL) and ForestTools/lidR/PyCrown/itcSegment (GPL) are method references only. The repository is MIT.
5. Phase 5 is planned. It needs maintainer approval before a tag, release, Pages setting change, or live deployment.
6. Phase 6 is planned. The first review should decide whether to add a planting-site entity, a work-order log, and a fitted local growth model.
7. Phases 0 to 4 merged as PR #36 (`1e0a9b0`). The parent issues #1 to #5 and their child issues #8 to #35 are closed. Subsequent hygiene commits on `main` fixed the editable-install ignore, the documentation package install, and the Pages deferral. CI and the Docs workflow are green on `main` as of `dc9f599`.
