# Lower Mainland city instances: Surrey, Burnaby, Coquitlam

Status: active P34 plan, 2026-11-06.

Parent issue: #149

## Goal

Add three independently mounted FRESH Urban Forest Lab model instances to the demo portal:
Surrey, Burnaby, and Coquitlam. Each instance uses public data only, keeps its own runtime
directory, and states its method and limitations in the portal card and dataset provenance.

This is a **provisional public-data compilation**, not a field-validated inventory. The
LiDAR and imagery datasets that Andrew described as pending delivery can replace the
provisional inputs later without changing the portal contract.

## What each instance needs

- A canonical dataset directory under `data/processed/` with a manifest, terrain, tree
  table, buildings, boundary, 2D map layers, 3D scene, and city metrics.
- A `PortalDemo` entry with an isolated runtime directory.
- A city-level method note and source/licence lock.
- A browser smoke check for 2D and 3D.

## Data sources and provisional methods

### Surrey

- Surrey Trees feature service: about 100,969 public street/park trees.
- Surrey Building Footprints: about 137,657 footprints, including `BUILDING_HEIGHT` and
  `GROUND_ELEVATION`.
- Surrey City Boundaries and Tree Canopy.
- Metro Vancouver Land Cover Classification 2020 (5 m) for conifer/deciduous/shrub context.
- Surrey contours for a provisional terrain surface.

Method: use the point inventory as the tree table. Surrey does not publish height/DBH in
this service, so height and crown width are **imputed** from land-cover class and the
existing allometry. This is labelled in the manifest and UI, not presented as measured.

### Burnaby

- Burnaby 2022 0.5 m DEM and DSM (public ZIP downloads).
- Burnaby Building Outlines with `HEIGHT`.
- Burnaby Boundary.
- Metro Vancouver Land Cover Classification 2020 for conifer/deciduous context.
- OSM road centrelines.

Method: derive CHM = DSM − DEM, detect individual-tree candidates with the existing
CHM detector, attach building heights from the building outline field, and assign
conifer/deciduous context from the land-cover raster. This is a LiDAR-derived candidate
layer, not a public-tree census.

### Coquitlam

- Coquitlam Buildings with `HEIGHT` and City Boundary.
- Coquitlam elevation points and contours for a provisional DEM.
- Metro Vancouver Land Cover Classification 2020 tree classes.

Method: use the 5 m land-cover tree classes to place a deterministic canopy-candidate
sample at a fixed grid spacing, with class-specific height and crown assumptions. Building
heights come from the City field. This is explicitly a **canopy-candidate** model until
the municipal LiDAR/imagery delivery is available; it is not an individual-tree inventory.

### Shared context

- OSM roads, ODbL 1.0, for the pale 2D street underlay and 3D road overlay.
- Open Government Licence – City of Surrey / City of Burnaby / City of Coquitlam.
- Open Government Licence – Metro Vancouver for LCC 2020.
- No owner names, addresses, parcel ownership claims, or private photos.

## Privacy and uncertainty

The instances show public tree/canopy and building data only. Land-cover classes are
context, not species identification. Imputed heights and crown widths are screening values.
The portal cards must say "provisional", "public data", and "not a census" where the tree
table is not a complete municipal inventory.

## Tasks

- P34.1 Generic city-instance pack contract and source lock.
- P34.2 Acquire and compile Surrey.
- P34.3 Acquire and compile Burnaby.
- P34.4 Acquire and compile Coquitlam.
- P34.5 Portal cards and browser verification.
- P34.6 Method notes, changelog, dashboard, and close-out.

## Acceptance

- `/surrey/`, `/burnaby/`, and `/coquitlam/` load their own datasets and runtime dirs.
- Each portal card shows its tree/canopy numbers and provisional-data label.
- 2D and 3D load without browser console or page errors.
- No dataset is written outside `/srv/shared-data`.
- `python scripts/dashboard.py` is green.
