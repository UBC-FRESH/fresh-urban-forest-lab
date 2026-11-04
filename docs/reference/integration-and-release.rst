Integration and the v0.3 release candidate
==========================================

P11 composes the shade, water, optimization, off-inventory, and bird layers into one
portable lab report. v0.3.0 is the released integrated lab.

Unified lab report
------------------

``GET /api/report?scenario_id=<id>&year=<year>`` returns one JSON bundle:

- dataset identity and source provenance;
- scenario identity and year;
- canopy metrics;
- inventory completeness;
- representative-day shade metrics;
- bird habitat, guild relative abundance, and prior demography;
- off-inventory summary, when present;
- an evidence list and explicit caveats.

The baseline report is the same endpoint with no scenario parameter.

.. code-block:: bash

   fresh-urban-forest report \
     --dataset data/demo/ubc_core \
     --scenario runtime/scenarios/<id>.json \
     --year 25 \
     --out tmp/lab-report.json

The browser button **Export lab report** downloads the bundle for the current scenario and
preview year. The baseline button exports the baseline report.

The report is a **composition**, not a new model. It keeps each layer's evidence tier and
caveats instead of collapsing them into one score.

v0.3 release candidate
----------------------

The integrated lab includes:

- P7 marginal shade, species fit, water, growth, and irrigation;
- P8 Fresh Solutions optimization and the fuzzy Pareto explorer;
- P9 off-inventory canopy and value of information;
- P10 bird habitat and prior demography;
- P11 unified report and browser export.

Version metadata is ``0.3.0``. The release notes are
``notes/releases/v0.3.0.md``.

Release
-------

v0.3.0 is tagged and published from the release commit. Future tags, releases, repository
settings changes, Pages changes, and public deployments remain approval-gated.

v0.3.0 is not a claim that every model is field-calibrated. Known gaps remain:

- no completed field shade or bird reference patch;
- no calibrated local growth model;
- bird demography is prior-driven;
- off-inventory ownership is unknown;
- the optimization archive is a finite weighted-scalarisation approximation;
- City LiDAR coverage is two core tiles, not the whole city.

Benchmark
---------

The whole-campus optimizer evidence remains:

- 387 candidate sites
- 72 scalarizations
- 1,010,952 exact evaluations
- 71 archive solutions
- hypervolume 0.0508
- 100.94 s on 8 workers

The Z* convergence run stopped on patience after 36 rounds and 112,116 evaluations, with a
best balanced scalar objective of -0.293285.

See ``notes/reports/p8-benchmark-evidence.json`` for the machine-readable record.
