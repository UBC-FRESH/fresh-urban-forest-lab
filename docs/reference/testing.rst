Testing and quality gates
=========================

The repository uses the UBC-FRESH green dashboard. Every commit leaves it green.

Run the dashboard
-----------------

.. code-block:: bash

   python scripts/dashboard.py

The dashboard runs:

- ``ruff check``
- ``ruff format --check``
- ``mypy`` in strict mode
- ``pytest`` with branch coverage
- ``scripts/check_workflow.py``
- ``sphinx-build -b html docs _build/html -W``

Test layers
-----------

.. list-table::
   :header-rows: 1

   * - Layer
     - Examples
   * - Unit
     - ``test_allometry``, ``test_models_metrics``, ``test_spatial``
   * - Contract
     - ``test_service``, ``test_dataset``, ``test_scene``
   * - Data ingestion
     - ``test_catalog_materialize``, ``test_tiles``, ``test_vancouver``
   * - Analysis
     - ``test_growth_dss``, ``test_change_product``, ``test_validation``
   * - Field workflow
     - ``test_field_packet``, ``test_field_analysis``
   * - Static shell
     - ``test_web_assets``
   * - CLI integration
     - ``test_urban_cli``
   * - Workflow self-check
     - ``test_workflow``, ``test_check_workflow``

The current suite has **232 tests** and a **85 percent** branch-coverage gate. The last
full run was above the gate.

Browser checks
--------------

The UI is checked with Playwright during development:

- load the shell
- switch 2D/3D/Change/Analytics
- create and project a scenario
- scrub the preview year
- switch change products
- open the assistant and send a question

Screenshots are retained locally under ``tmp/screens`` and are not tracked.

What the tests do not prove
---------------------------

- field accuracy of a detected crown;
- species identification accuracy;
- annual growth accuracy;
- multi-user concurrency;
- browser behaviour on every device.

Those are recorded as known gaps rather than implied by a green test suite.

CI
--

CI runs the quality gates on every pull request and push to ``main``. The Docs workflow
builds the Sphinx site with warnings as errors and deploys the Pages artifact when Pages is
enabled.
