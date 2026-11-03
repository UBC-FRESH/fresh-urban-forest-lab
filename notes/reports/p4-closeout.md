# Phase 4 close-out: Verify and demo

Status: queued for maintainer review
Date: 2026-11-03

## What was delivered

- A standalone Python package (`fresh_urban_forest`) with typed dataset, tree, scenario,
  and result contracts.
- A source catalog and resumable, hashed materialization path.
- UBC and City of Vancouver tree adapters; raster and LAZ ingestion; canopy metrics.
- A transparent allometric growth model, carbon estimate, scenario projection, DSS score,
  and explainable planting recommendations.
- CHM individual-tree detection and repeat-measures canopy change.
- A FastAPI service, a MapLibre 2D map, and a Three.js 3D terrain and instanced-tree
  scene with shared selection and editing.
- A tracked UBC core-campus demo dataset and a full UBC 2021 dataset built locally.
- Documentation, method notes, data licences, and a software-landscape review.

## Evidence

Commands run on the head commit:

```text
python -m ruff check src scripts tests        -> All checks passed
python -m ruff format --check src scripts tests -> clean
python -m mypy                                 -> Success: no issues found in 38 source files
python -m pytest -q                            -> 190 passed; 87.55% branch coverage
python scripts/check_workflow.py               -> 0 errors
sphinx-build -b html docs _build/html -W       -> build succeeded
python scripts/dashboard.py                    -> OVERALL: GREEN
```

Real-data build:

```text
fresh-urban-forest build --ubc-trees ... --dem DEM_1m.tif --chm CHM_1m.tif ...
  -> 9,324 tree records
  -> 9,259 live trees
  -> 66.563% raster canopy cover
  -> 294,201,110.558 m3 raster canopy volume
  -> 3,822,188.263 kg above-ground carbon
```

Browser check: Chromium loaded the 2D map and the 3D scene. The final run reported
`status LIVE` and no console errors. Screenshots were written to a local `tmp/screens/`
directory and are not tracked.

## What was not verified

- The full Metro Vancouver 2022 classified LiDAR was cataloged but not downloaded (about
  16.5 GB).
- The City of Vancouver 2013/2018/2022 repeat series was not built into a change product.
- A calibrated local growth model was not fitted; the current growth model is generic and
  transparent.
- The tree inventory's missing attributes are imputed, not measured. The completeness rate
  is recorded in the data note but not yet displayed in the UI.
- The demo is a downsampled core-campus snapshot, not full coverage.

## Approval gates

The following need explicit maintainer approval and were **not** done:

- creating a tag or GitHub release;
- enabling or changing GitHub Pages, branch protection, or repository settings;
- deploying a public live demo or a server;
- publishing an announcement.

The repository itself was created public at the maintainer's request.

## Recommended next actions

1. Approve or amend this report.
2. Open Phase 5: write release notes, check Pages, and tag v0.1.0.
3. In Phase 5 or 6, add a first-class planting-site entity and a work-history log.
4. Fit local height-diameter and growth curves from repeat UBC measurements; keep the
   generic model as the fallback.
5. Add the City 2018/2022 and UBC 2015 change series with a leaf-on/leaf-off caveat.
