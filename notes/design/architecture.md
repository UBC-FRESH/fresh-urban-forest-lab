# Architecture of the prototype

Status: design note, 2026-11-03.

## Intent

Build one small, auditable stack that can answer: what canopy is there, how is it
changing, and what would a management scenario do? The stack must run on a laptop with no
runtime dependency on another research system, and it must make its data lineage and
method assumptions visible.

## Layers

```text
public sources
  -> catalog + resumable materialization (catalog.py, materialize.py)
  -> normalised tree records + aligned rasters (inventory.py, terrain.py, lidar.py)
  -> portable dataset directory (dataset.py; manifest.json is the contract)
  -> metrics / growth / DSS (metrics.py, growth.py, dss.py)
  -> scene payload (scene.py)
  -> FastAPI + MapLibre + Three.js (service.py, web/static/)
```

### Data contracts

- `TreeRecord`: one tree, with source, date, native flag, projected coordinates,
  elevation, LiDAR height, and a free-form attribute map.
- `TerrainGrid`: projected bounds, cell counts, elevation, and canopy height.
- `DatasetManifest`: dataset id, CRS, bounds, sources, metrics, and a file map.
- `ScenarioEdit`: an append-only typed edit.
- `Scenario`: base dataset + ordered edits + horizon + revision.
- `ScenarioResult`: metrics per year, final trees, cost, score, notes.

The contracts are frozen dataclasses with explicit optional fields. JSON serialisers sit
next to them so the browser and the CLI read the same shapes.

### Why a dataset directory instead of a database

The pilot is a single-user research prototype. A directory of JSON, NumPy, and GeoJSON is
reviewable, diffable, portable, and easy to archive. A database becomes necessary when
there are concurrent editors, roles, or per-tree work orders; that is a later phase.

### Why no hard dependency on femic, nemora, fhops, ws4, or fresh-fvsbc

Those systems are excellent sources of design patterns and, in the case of `fresh-fvsbc`,
a possible growth engine. But each brings its own release cadence, optional dependencies,
and domain assumptions. This prototype copies the *shape* of their best ideas:

- FEMIC's catalog → selection manifest → resumable, hashed materialization;
- Nemora's small dataset descriptor and transform pipeline;
- FHOPS's validated edit pattern and glTF tree scene;
- WS4's compiled-dataset manifest and target/objective language;
- fresh-fvsbc's tree-list/provenance discipline.

If a later phase needs FVS growth, `fresh-fvsbc` can be an optional extra behind an
adapter. The core contracts do not import it.

## 2D and 3D

- One scene payload carries `origin_lonlat`, `meters_per_degree`, WGS84 bounds, local
  metres, terrain arrays, trees, buildings, and the boundary.
- MapLibre draws a local hillshade and canopy PNG over the campus, then vector buildings
  and tree points. It never needs an external basemap tile.
- Three.js draws a heightfield terrain mesh and instanced trunks and crowns. Tree picks
  use a raycaster against the instanced meshes; the instance id maps back to `TreeRecord`.
- Selection is shared state: selecting a tree on either view updates the inspector and the
  other view.

## Scenario flow

1. The client holds a draft edit list.
2. The first preview creates a scenario; later previews append only new edits with a
   revision check.
3. The server applies edits, grows the population year by year, and records a metric
   snapshot per year.
4. Year-zero cover and volume are reconciled with the raster baseline using an additive
   offset, so a scenario starts at the published canopy value rather than at the much
   smaller inventory-only crown area.
5. The result is cached in memory; scenario JSON is persisted atomically.

## Deliberate simplifications

- One projected CRS per dataset; no on-the-fly reprojection of rasters.
- No point-cloud ground classification beyond trusting ASPRS class 2; the 2021 tile is
  mostly unclassified plus ground.
- No species-specific calibrated growth curve; a transparent group profile is used until
  local repeat measurements are available.
- No multi-user auth, work orders, or risk assessment.
- The demo is a downsampled core-campus snapshot, not the full source coverage.

## Assistant

The `+ Ask` pill opens a pop-up chat panel. The browser sends the message, an optional
session id, and a compact context object (view, dataset, selected tree, scenario, metrics,
and recommendation count). The FastAPI service runs the local `opencode` CLI with a
sanitized environment and returns the parsed text, session id, and tool-action chips. The
assistant is opt-in (`--allow-agent`), has a configurable model and timeout, and never
gets cloud or session credentials from the parent process. It is a local research aid.
The deployment boundary is the Cloudflare Zero Trust gateway with UBC CWL that fronts the
whole dev server; the app itself does not add a second login layer, and the raw port must
not be exposed directly.

## Extension points

- `growth.py`: swap the allometric model for an adapter over `fresh-fvsbc` or a fitted
  local model.
- `itd.py`: add a point-cloud-based segmentation or a Dalponte-style region-growing
  variant.
- `catalog.py`: add a BC Data Catalogue or Metro Vancouver tile resolver.
- `service.py`: add a job queue and SSE progress for long projections or large imports.
- `web/static/app.js`: add saved views, filters, and a planting-site entity.
