Project status and repository map
=================================

Status as of 2026-11-09:

- The mainline is complete through Phase 55; P37 remains a separate workstream.
- v0.4.0 is released. P30 adds a full-City-of-Vancouver public-data pilot; P38–P46
  add shade/equity, gap, heat, change, action, and turnover screens; P47–P49 add the
  Optimization and site-scenario explorers; P50–P55 add full-city vertical control and
  corrected change/action/turnover layers.
- The documentation site remains live on GitHub Pages. See :doc:`research-agenda`,
  :doc:`shade-and-species`, :doc:`optimization-and-pareto`, :doc:`site-scenarios`,
  :doc:`off-inventory-canopy`, :doc:`bird-habitat-and-demography`,
  :doc:`change-products`, :doc:`vancouver-city-pilot`, and :doc:`integration-and-release`.

The live plan is ``ROADMAP.md`` and the GitHub issues. The dated narrative is
``CHANGE_LOG.md``.

Repository map
--------------

.. list-table::
   :header-rows: 1

   * - Path
     - Purpose
   * - ``src/fresh_urban_forest/``
     - Typed core, CLI, FastAPI service, vendored web assets.
   * - ``data/demo/ubc_core/``
     - Small derived UBC core demo and change products.
   * - ``docs/``
     - This Sphinx site.
   * - ``notes/``
     - ADRs, source notes, design notes, reports, release notes.
   * - ``scripts/``
     - Workflow validator, dashboard, browser tile helper.
   * - ``tests/``
     - Unit, contract, data, analysis, field, static, CLI, and workflow tests.
   * - ``DATA_LICENSES.md``
     - Source licences and attribution.
   * - ``CITATION.cff``
     - Citation metadata for v0.3.0.
   * - ``AGENTS.md``
     - The coding-agent contract.

What is in the PoC
------------------

- source catalog and resumable materialization
- UBC and Vancouver inventory adapters
- UBC 2021 dataset build
- LidarBC, CanElevation, and City tile discovery
- UBC 2015/2016/2021 observed change on a common mask
- City 2018/2022 observed change
- inventory completeness and measured/imputed flags
- CHM detection, tuning, and validation
- field packet and field analysis
- local height-diameter calibration
- scenario edits, growth, cost, score, planting advisor, and zone search
- 2D map, 3D scene, change tab, analytics, time animation, exports
- local assistant

Known gaps
----------

- No completed field reference patch.
- No repeat measurements for annual growth calibration.
- City coverage is two core tiles, not the whole city.
- No accounts, work orders, risk assessment, or mobile field app.

Release actions
---------------

The v0.3.0 tag and GitHub release are complete. Future tag, release, Pages, repository
settings, public deployment, and announcement actions need explicit maintainer approval.

The repository itself is public by design.
