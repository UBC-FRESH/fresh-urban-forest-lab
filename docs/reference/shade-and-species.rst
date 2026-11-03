Shade, species fit, water, and irrigation
=========================================

P7 adds a tree-level light and water layer. It answers a narrower and more useful question
than canopy cover: **how much additional shade does this tree actually create, at this
place and time, given the buildings and canopy already there?**

The method is a planning screen. It is not a temperature model, a field-validated shade
survey, or a calibrated local growth model.

Marginal shade
--------------

A tree in a closed canopy or deep building shadow can have a large crown and almost no
marginal effect on pedestrian shade. A spaced street tree can have a smaller crown and a
large marginal effect. The engine therefore separates:

- **building shade** — cast by extruded building footprints;
- **tree shade** — cast by existing tree crowns;
- **terrain shade** — an optional coarse terrain horizon;
- **overlap** — cells shaded by both a building and a tree;
- **marginal tree shade** — cells that become shaded only when a selected tree is added.

The marginal layer is the decision signal. It is not the same as canopy area.

Solar and shadow method
-----------------------

- The solar position uses the NOAA equations, evaluated in UTC and displayed in the local
  timezone.
- Building footprints are projected along the solar vector; tree crowns are ellipses with
  a crown width and live-crown depth.
- The kernel targets a horizontal plane at 1.5 m by default. A facade or roof target is a
  future extension.
- A coarse eight-direction terrain horizon is available for small grids.
- Shadows are accumulated over representative times or an annual sample. The annual
  estimate scales the sampled shade fraction by 365 days and mean daylight hours.

The kernel is deliberately 2.5-D: no penumbra, no leaf transmissivity, no full 3D facade
geometry, and no computational fluid dynamics. A future Radiance or SOLWEIG comparison is
the validation benchmark, not a runtime dependency.

Species fit
-----------

A transparent trait table covers common Vancouver and Pacific Northwest species. Traits
include light demand, drought tolerance, water use, minimum soil volume, mature size,
native status, salt/heat/flood tolerance, allergen risk, and BVOC risk.

The site-fit score combines:

- light match against the species' preferred sun fraction;
- water demand against available water;
- soil volume against the species minimum;
- heat exposure against heat tolerance;
- available space against mature crown width.

Each fit returns a score, limiting factors, and an evidence tier. Unknown species fall back
to a conifer, deciduous, or unknown group profile.

Water and growth
----------------

The water model is a single soil bucket per tree:

- rainfall captured by the crown fills the bucket;
- evapotranspiration draws it down;
- irrigation refills it under a selected policy;
- overflow becomes runoff;
- days below a stress threshold are counted.

Irrigation policies are none, establishment, fixed, moisture-triggered, and deficit. Each
policy returns water volume, stress days, visits, annual cost, and cost per effective
shade-hour. Water price, labour rate, and visit frequency are configurable assumptions, not
a utility bill.

Growth and vigour use a multiplier stack for light, water, heat, soil, and competition.
The projection is labelled ``scenario`` unless a local calibration exists. This is not a
drought-mortality model.

Evidence tiers
--------------

Every output names one of:

- ``measured`` — field or inventory measurement;
- ``physics`` — deterministic solar/shadow geometry;
- ``calibrated`` — fitted to local observations;
- ``scenario`` — model projection with stated assumptions;
- ``prior`` — literature or expert prior, not locally validated.

The solar and shadow outputs are ``physics``. Species fit and water balance are ``prior``.
Growth and irrigation cost are ``scenario``.

API
---

.. list-table::
   :header-rows: 1

   * - Endpoint
     - Purpose
   * - ``GET /api/solar``
     - Solar position for a date and time.
   * - ``GET /api/shade``
     - Shade metrics and image metadata for an instant, day, or annual sample.
   * - ``GET /api/shade.png``
     - Aggregated shade overlay.
   * - ``GET /api/light/tree/{id}``
     - Tree shade card, species fit, water, irrigation, and growth.
   * - ``GET /api/species``
     - Built-in trait profiles.
   * - ``GET /api/species/fit``
     - Site-fit score for one species.
   * - ``GET /api/water``
     - Annual water balance and policy comparison.
   * - ``GET /api/irrigation``
     - Irrigation options and cost per shade-hour.

CLI
---

.. code-block:: bash

   fresh-urban-forest shade \
     --dataset data/demo/ubc_core \
     --date 2026-06-21 \
     --mode day \
     --times 09:00,12:00,15:00 \
     --out-dir tmp/shade

   fresh-urban-forest species-fit \
     --dataset data/demo/ubc_core \
     --species "Acer rubrum" \
     --out tmp/fit.json

   fresh-urban-forest water \
     --dataset data/demo/ubc_core \
     --species "Acer rubrum" \
     --out tmp/water.json

   fresh-urban-forest irrigation \
     --dataset data/demo/ubc_core \
     --species "Acer rubrum" \
     --out tmp/irrigation.json

Web UI
------

The **Light** tab shows a georeferenced shadow overlay, date and time controls, a period
selector, and a 3D sun position. The selected tree card shows marginal shade, shade
efficiency, species fit, vigour, stress days, water cost, and the best irrigation policy.
The map separates building shade, tree shade, overlap, and terrain shade in its legend.

.. image:: /_static/light-shadow.png
   :alt: Light tab with building and tree shade on the UBC core demo
   :width: 100%

.. image:: /_static/tree-light-card.png
   :alt: Selected-tree shade, species, water, and irrigation card
   :width: 100%

Limitations
-----------

- Crowns are ellipses; buildings are extruded footprints.
- Penumbra, leaf transmissivity, facade geometry, and wind are not modelled.
- The terrain horizon is coarse and only evaluated for small grids.
- Species traits and the default climate are priors, not local measurements.
- Growth is not calibrated to repeat measurements.
- The VPD, soil texture, rooting volume, and irrigation efficiency are simplified.
- The result is a screening and prioritization surface, not a shade or cooling measurement.

Validation and provenance are recorded in
``notes/reference/shade-review-protocol.md`` and
``notes/reports/p7-shade-species.md``.
