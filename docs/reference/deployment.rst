Deployment and operations
=========================

Local demo
----------

.. code-block:: bash

   python -m venv .venv
   . .venv/bin/activate
   python -m pip install -e ".[dev,web]"
   fresh-urban-forest serve --dataset data/demo/ubc_core --port 8000

The service binds ``127.0.0.1`` by default. A non-loopback bind requires
``--allow-remote``.

Path-prefixed reverse proxy
---------------------------

All static and API URLs are relative, so the app works under a path prefix such as:

.. code-block:: text

   https://host.example/user/name/codeserver/proxy/8101/

The shell, ``app.js``, and ``styles.css`` are served with ``Cache-Control: no-store``.
Change images carry a content-hash query parameter. This prevents a rebuilt raster from
being masked by a stale browser cache.

Remote access
-------------

The reference deployment is behind a Cloudflare Zero Trust gateway with UBC CWL. That
gateway is the authentication boundary for the entire dev server, including the assistant.
The application does not add a second login layer.

Do not expose the raw service port directly. If the app is placed on a new host, put it
behind the same gateway policy and record the change.

GitHub Pages
------------

The repository has a Sphinx documentation site. Publishing it requires two steps:

1. Enable GitHub Pages with the GitHub Actions build source.
2. Keep the deploy job in ``.github/workflows/docs.yml``.

The workflow builds with warnings as errors, uploads ``_build/html``, and deploys the
artifact. The published URL is:

.. code-block:: text

   https://ubc-fresh.github.io/fresh-urban-forest-lab/

``llms.txt`` is copied to the site root as an agent-facing index.

Data storage
------------

- ``data/demo/`` is tracked and small enough for a clean clone.
- ``data/raw/`` and ``data/processed/`` are gitignored.
- ``runtime/`` holds scenario JSON, exports, and the server log; it is gitignored.
- The full UBC 2021 LiDAR, UBC 2015 tiles, and City 2018/2022 tiles stay outside git.

Backup
------

Back up:

- ``data/processed/`` if it contains rebuilt products not reproducible from a manifest.
- ``runtime/scenarios/`` if users created scenarios worth keeping.
- ``notes/`` and ``docs/`` with the repository.

Dataset and change products are reproducible from the catalog and the recorded commands.

Upgrade
-------

1. Pull the repository.
2. Reinstall with ``python -m pip install -e ".[dev,web]"``.
3. Run ``python scripts/dashboard.py``.
4. Restart ``serve``.
5. Rebuild any dataset or change product whose source code changed.

The dataset schema version is ``fresh-urban-forest.dataset.v1``. Any schema change needs a
changelog entry and a migration note.

Health checks
-------------

.. code-block:: bash

   curl http://127.0.0.1:8000/api/health
   curl http://127.0.0.1:8000/api/dataset
   curl http://127.0.0.1:8000/api/completeness
   curl http://127.0.0.1:8000/api/changes

The health response names the dataset id. A missing dataset or a missing static directory
is a startup error, not a silent fallback.

Release gates
-------------

Tag, GitHub release, Pages settings, and branch protection are approval-gated actions.
A release candidate must have a green dashboard, a green CI run, a docs build, a clean-clone
demo check, and a written known-gaps list.
