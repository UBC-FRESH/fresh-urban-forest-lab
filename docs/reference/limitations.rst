Limitations and known gaps
==========================

This page is the honest boundary of the prototype. A capability not listed in the roadmap
or documented here should not be assumed.

Scientific limits
-----------------

- **Growth is a scenario model**, not a calibrated local growth model. Annual increment
  comes from a transparent species-group curve with a crown-light-exposure adjustment.
- **Carbon is above-ground only**, using generalized Jenkins equations. Roots, dead wood,
  and soil carbon are excluded.
- **Canopy volume** is an ellipsoid crown sum at tree level and a height-field prism at
  raster level. It is not a quantitative structure model.
- **Detection is CHM-based** local maxima plus watershed. Dense multi-layer stands, steep
  terrain, and overlapping crowns will merge or split.
- **Observed change is a screening surface.** Acquisition season, vertical datum, returns,
  and classification differ between dates.
- **Inventory completeness is low** for DBH, height, and crown width. The demo is about
  53 percent measured for each.
- **No field-verified reference patch has been completed yet.** The Main Mall packet is
  ready, but the analysis is pending field work.
- **No annual growth calibration** is possible from the current inventory because no tree
  has repeat measurements.

Data and coverage limits
------------------------

- The demo is a downsampled core-campus snapshot, not full UBC or Metro Vancouver coverage.
- The 2016 UBC change product uses four core tiles; the 2015 product uses four other core
  tiles. They now share a common 2 km mask for comparison.
- The Vancouver pilot is citywide: 2022 LiDAR plus 181 2018 LiDAR tiles. P37
  Surrey/Coquitlam remains a separate workstream.
- Corrected change/action/turnover products are screening layers, not final citywide
  net-change claims.
- The CanElevation tile index is about 428 MB and is not tracked.
- The City download host requires a browser challenge; the manifest and browser helper are
  the workaround.
- The full raw and processed LiDAR products stay outside git.

Product limits
--------------

- No user accounts, roles, or multi-user editing.
- No work orders, risk assessment, photo attachments, or 311 integration.
- No mobile offline field app; the field packet is CSV and GeoJSON.
- No public multi-tenant deployment.
- No species identification from imagery.
- No terrestrial laser scanning or QSM.
- No i-Tree benefit-transfer engine.

Operational limits
------------------

- The assistant can run local shell commands and has no app-level login. It relies on the
  Cloudflare/CWL gateway.
- Scenario state is file-based; there is no database or optimistic concurrency beyond the
  revision number.
- The 3D scene uses procedural crowns and a display terrain mesh, not survey geometry.
- Browser performance is untested at full city scale.

Release limits
--------------

- v0.5.0 is a research prototype, not a final product.
- Future tag, GitHub release, Pages setting, or branch-protection changes need explicit
  approval.
