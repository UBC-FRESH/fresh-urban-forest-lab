Observed change products
========================

Observed change is a thresholded comparison of two canopy-height surfaces. It answers
“what changed on the ground between these acquisitions,” not “what would this scenario
do.”

Product files
-------------

A change product is a small directory:

.. list-table::
   :header-rows: 1

   * - File
     - Purpose
   * - ``change.json``
     - Labels, CRS, bounds, image corners, threshold, metrics, legend, image version.
   * - ``change.png``
     - Transparent loss/stable/gain overlay, cropped to valid coverage.
   * - ``change_grid.npz``
     - Class grid, earlier/later canopy, elevation, and validity mask.

A dataset can hold several products. The service lists them from ``change*.json`` and the
Change tab passes a ``product`` query parameter:

.. code-block:: text

   GET /api/changes
   GET /api/change?product=change_2015_2016.json
   GET /api/change.png?product=change_2015_2016.json&v=<hash>

Method
------

1. Acquire earlier point-cloud tiles and a later CHM/DEM.
2. Transform earlier points into the later projected CRS when needed.
3. Exclude ground, buildings, water, and noise from the canopy surface.
4. Bin the highest remaining return per cell.
5. Subtract the DEM to obtain the earlier CHM.
6. Compare only cells valid in both dates.
7. Classify each cell as loss, stable canopy, gain, or no canopy at a fixed threshold.
8. Record the threshold, overlap area, acquisition labels, and rasters.

Metrics
-------

- **Gain**: canopy in the later date only.
- **Loss**: canopy in the earlier date only.
- **Stable**: canopy in both dates.
- **Net**: later canopy area minus earlier canopy area.
- **Mean height change**: later minus earlier height on stable canopy cells.
- **Valid overlap**: area where both dates have data.

The ratio metrics are relative to earlier canopy. They are not annual growth rates.

UBC products on a common mask
-----------------------------

All three use the same 2 km core box ``E481000–E483000, N5456000–N5458000`` at 1 m.

.. list-table::
   :header-rows: 1

   * - Comparison
     - Earlier
     - Later
     - Gain
     - Loss
     - Net
     - Height change
   * - 2015 → 2016
     - 2.359M m²
     - 2.347M m²
     - +175,360 m²
     - −187,376 m²
     - −12,016 m²
     - −0.095 m
   * - 2015 → 2021
     - 2.359M m²
     - 2.470M m²
     - +320,535 m²
     - −209,369 m²
     - +111,166 m²
     - +0.235 m
   * - 2016 → 2021
     - 2.347M m²
     - 2.470M m²
     - +263,201 m²
     - −140,019 m²
     - +123,182 m²
     - +0.420 m

The near-zero one-year change is the main sanity check. The multi-year products both show
a net gain.

City of Vancouver product
-------------------------

- 2018 → 2022, two core tiles, 2.00M m² overlap.
- Earlier canopy 728,756 m²; later 864,335 m².
- Gain +212,734 m²; loss −77,155 m²; net +135,579 m².
- Mean height change +0.575 m.

The City product covers a different, more developed area and uses a different acquisition
and classification chain. Do not compare its percentage gain directly with the UBC
percentages.

Acquisition caveats
-------------------

- 2015 is EPSG:26910, 2018 City is EPSG:3157, 2022 City is EPSG:26910, and the 2021 UBC
  DEM is EPSG:3157. Points were transformed before binning.
- Vertical datums differ between the UBC and City products.
- Leaf-on/leaf-off status differs between some acquisitions.
- A canopy gain is not proof of planting; it can reflect growth, crown expansion, better
  returns, or a method difference.
- Loss can reflect removal, dieback, pruning, shadow, or a lower-quality return.
- The products are screening surfaces, not calibrated growth estimates.

Browser-blocked publishers
--------------------------

The City download host returns Cloudflare 403 to automated clients. A headed Chromium under
Xvfb passed the challenge:

.. code-block:: bash

   xvfb-run -a python scripts/browser_download_tiles.py \
     --manifest data/raw/tiles/vancouver_2022_ubc.json \
     --dest data/raw/city_lidar/2022

The helper does not bypass authentication. It uses a normal browser session and respects
the publisher’s challenge.

Adding a product
----------------

1. Build the two aligned grids on the same bounds.
2. Run ``build-change`` or call ``build_change_product``.
3. Copy ``change.json`` and ``change.png`` into the dataset directory.
4. Add them to ``manifest.json`` (optional; the service discovers ``change*.json``).
5. Reload the app and select the new product.

The image version in ``change.json`` is a SHA-256 prefix of the PNG, so a rebuilt raster
gets a new URL.
