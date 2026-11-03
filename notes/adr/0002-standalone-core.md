# ADR 0002: Keep the core standalone and borrow patterns, not hard dependencies

Status: accepted
Date: 2026-11-03

## Context

The lab has strong systems in `femic`, `nemora`, `fhops`, `ws4`, `fresh-hectaresbc`, and
`fresh-fvsbc`. Depending on them directly would bring release cadence, optional
dependencies, and domain assumptions into a public prototype that needs to stay easy to
run and easy to change.

## Decision

Implement the urban-forest core in this repository with a small, permissively licensed
dependency set (NumPy, pandas, rasterio, laspy, pyproj, shapely, scipy, FastAPI, Typer,
Pillow). Copy or reimplement the patterns we need:

- FEMIC's resumable, hashed materialization;
- FHOPS's validated edits and instanced tree scene;
- WS4's compiled-dataset manifest and target language;
- fresh-fvsbc's provenance discipline.

Keep `fresh-fvsbc` as an optional future adapter, not a core import.

## Consequences

- The prototype installs and runs without the rest of the lab stack.
- We own the maintenance of the small core.
- If an upstream system solves a problem better, we can add an adapter without changing the
  data contracts.
- We must cite the design lineage and avoid copying copyleft code.
