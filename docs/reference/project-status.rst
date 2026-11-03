Project status and repository map
=================================

Status as of 2026-11-03:

- Phase 0–4 are complete on ``main``.
- Phase 5 is a **v0.2.0 release candidate**. The tag, GitHub release, and Pages settings
  change are approval-gated.
- Phase 6 (operate and maintain) is planned.

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
     - Citation metadata for v0.2.0.
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
- No tagged release yet. The documentation site is live on GitHub Pages.
- P7-P11 are queued as planned phases. See :doc:`research-agenda`.

Release actions
---------------

The following need explicit maintainer approval:

- create a tag or GitHub release
- enable or change GitHub Pages
- change repository visibility, settings, or branch protection
- deploy a public live demo
- publish an announcement

The repository itself is public by design.
