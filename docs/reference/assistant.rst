Local assistant
===============

The **+ Ask** pill opens a pop-up chat panel. The assistant is a local research aid, not a
hosted model service and not a second authentication layer.

Endpoints
---------

``GET /api/agent``
   Returns whether the assistant is enabled, the model id, the workspace, whether
   ``opencode`` is on the PATH, and the timeout.

``POST /api/agent/chat``
   Body: ``message``, optional ``session``, optional ``context`` object.
   Returns: ``reply``, ``session``, and tool ``actions``.

Context sent by the browser
---------------------------

- active view and dataset id
- baseline metrics
- selected tree, including species, DBH, height, crown, native flag, carbon
- scenario id, edit count, horizon
- projected score, cost, baseline/final metrics, notes
- recommendation count

The context is truncated to 5,000 characters before it is added to the prompt.

Runtime
-------

The service runs:

.. code-block:: text

   opencode run --model <model> --format json --auto [--session <ses...>] <prompt>

It parses JSON-lines events for text, session id, tool actions, and errors. The default
model is ``opencode-go/deepseek-v4.1-flash``. ``--agent-timeout`` controls the subprocess
timeout.

Enable it with:

.. code-block:: bash

   fresh-urban-forest serve --dataset data/demo/ubc_core --allow-agent

Environment
-----------

``_agent_environment`` copies the parent environment, prepends ``<workspace>/src`` to
``PYTHONPATH``, sets ``FRESH_URBAN_FOREST_WORKSPACE``, and removes session and cloud
credentials such as ``OPENCODE_SESSION_ID``, AWS keys, S3 endpoints, and Globus tokens.

Security boundary
-----------------

The assistant has no application-level login. The deployment boundary is the Cloudflare
Zero Trust gateway with UBC CWL that fronts the whole dev server. Keep the raw service port
behind that gateway and do not expose it directly.

The assistant can run local shell commands through ``opencode``. Treat it as a trusted
colleague with shell access, not as a sandbox.

What it is good at
------------------

- explaining the current dataset, scenario, and metrics
- reading the repository docs and methods
- suggesting UI steps and planting priorities
- summarizing trade-offs and caveats

What it must not claim
----------------------

- that it changed the UI or saved a scenario
- that a generic allometric projection is calibrated
- that a detected crown is a verified tree
- that an observed-change product is a growth rate
