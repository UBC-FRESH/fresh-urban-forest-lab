Software landscape
==================

The project deliberately avoids hard dependencies on other lab systems or on GPL research
code. The long note is ``notes/reference/software-landscape.md``. This page is the short
version.

What we borrowed
----------------

- OpenTreeMap: tree versus planting-site separation, per-tree edit history, public map.
- TreeKeeper and TreePlotter: inventory + map + work records + exports as the operator
  surface. We implement inventory, scenarios, and exports; work orders are future scope.
- i-Tree Eco: biomass equations, crown-light-exposure adjustment, and the discipline of
  naming every input variable.
- ForestTools, lidR, PyCrown, itcSegment: local maxima plus watershed crown segmentation.
  Reimplemented from the published method with ``scipy.ndimage``.
- Treepedia: street-level Green View Index as a future layer. Not implemented because it
  needs proprietary Street View imagery.
- UBC-FRESH systems: FEMIC materialization, FHOPS edits and scene, WS4 manifests, and
  fresh-fvsbc provenance.

What we refused to copy
-----------------------

- AGPL code from OpenTreeMap.
- GPL code from ForestTools, lidR, PyCrown, or itcSegment.
- A hard runtime dependency on femic, nemora, fhops, ws4, fresh-hectaresbc, or
  fresh-fvsbc.
- A proprietary basemap or street-view service.

The repository is MIT. Data keep their own licences, listed in ``DATA_LICENSES.md``.
