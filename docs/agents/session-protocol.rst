Agent session protocol
======================

This project uses the UBC-FRESH dev workflow. The root ``AGENTS.md`` is the contract; this
page is the short operational version.

Start a session
---------------

1. Read ``AGENTS.md``.
2. Read ``ROADMAP.md`` and its "Detailed Next Steps Notes".
3. Read the latest ``CHANGE_LOG.md`` entries.
4. Read the note and docs page named by the task.
5. Audit the repository and GitHub read-only before changing anything.

Make a bounded move
-------------------

- One task at a time. State the task id, the expected change, and the verification.
- Keep domain rules in this repository's ``AGENTS.md`` and docs, not in the seed.
- Do not add a hard dependency on another lab system without an ADR.
- Do not copy copyleft code into an MIT repository. Reimplement the method and cite it.

Verify
------

Run the green dashboard before reporting done:

.. code-block:: bash

   python scripts/dashboard.py

It runs lint, format, strict types, tests with the coverage gate, the workflow validator,
and the Sphinx build with warnings as errors. A red gate is fixed before the next task.

Hand off
--------

- Update ``ROADMAP.md``, ``CHANGE_LOG.md``, the relevant note, and the task issue in the
  same change set.
- Record what you did not verify and why.
- Post a closeout comment before closing an issue.

Project-specific guardrails
---------------------------

- Do not present an allometric estimate as a measurement.
- Do not present a change comparison without the acquisition dates and canopy threshold.
- Keep the demo dataset small and derived; do not commit the raw LiDAR products.
- Keep the web shell offline-capable; vendor its JavaScript assets.
- Do not describe the prototype as an i-Tree replacement or a calibrated FVS model.
