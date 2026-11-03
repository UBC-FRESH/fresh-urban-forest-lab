Reproducibility and provenance
==============================

Every product records its inputs and the command that produced it. The goal is that a new
session can rebuild the demo or audit a change product without reading this conversation.

Source catalog
--------------

``src/fresh_urban_forest/resources/sources.yaml`` records:

- source id
- title and publisher
- landing page and direct URL
- licence
- native CRS
- products
- caveats

The catalog is a curated decision, not a scrape. A new source is added with its licence and
native CRS before it is used.

Materialization
---------------

``materialize.py`` writes a record for every download:

- source id and URL
- status
- byte count
- SHA-256
- attempts and resumed offset
- retrieval timestamp
- error text on failure

The manifest is written after each source, so an interrupted fetch can be resumed.

Dataset lineage
---------------

``manifest.json`` records:

- dataset id and schema version
- CRS and bounds
- tree count
- source records with licences
- baseline metrics
- file map

The tree table carries the source and a measured/imputed flag for DBH, height, crown width,
and species.

Change lineage
--------------

``change.json`` records:

- earlier and later labels
- CRS and bounds
- image corners and dimensions
- threshold
- valid overlap
- metrics
- legend
- image version (SHA-256 prefix)

The PNG has a content-hash query parameter. The service sends ``no-store`` so a stale image
cannot hide a rebuilt raster.

Reproduction commands
---------------------

.. code-block:: bash

   # install
   python -m pip install -e ".[dev,web]"

   # checks
   python scripts/dashboard.py

   # demo
   fresh-urban-forest serve --dataset data/demo/ubc_core --port 8000

   # rebuild the UBC dataset
   fresh-urban-forest build ... --out data/processed/ubc_lidar_2021

   # rebuild a change product
   fresh-urban-forest build-change --earlier ... --later ... --out-dir ...

   # detection validation
   fresh-urban-forest validate-detection ... --out-dir ...

   # field packet
   fresh-urban-forest field-packet ... --out-dir ...

   # allometry
   fresh-urban-forest fit-allometry --dataset ... --out ...

What is tracked
---------------

Tracked:

- source code, tests, docs, notes
- the small derived demo dataset
- change JSON/PNG products for the demo
- allometry JSON for the demo

Not tracked:

- raw LiDAR tiles
- full processed datasets
- runtime scenarios and logs
- field packet outputs
- temporary screenshots

Audit trail
-----------

- ``CHANGE_LOG.md``: dated narrative, newest last.
- ``ROADMAP.md``: phases, tasks, issue map, and next steps.
- ``notes/reports/``: phase close-outs and focused reports.
- GitHub issues: live status and closeout comments.
- ``docs/``: the RTFM surface built from this repository.

Citing data
-----------

Each source keeps its own licence. See ``DATA_LICENSES.md`` in the repository root and
:doc:`../guides/data`. Cite the UBC 2021 LiDAR, UBC tree inventory, City of Vancouver
products, and LidarBC as separate sources.
