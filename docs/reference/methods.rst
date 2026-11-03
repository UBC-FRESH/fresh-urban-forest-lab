Methods and assumptions
=======================

The prototype is deliberately explicit about what it measures and what it estimates. This
page is the short contract. The long rationale is in ``notes/design/architecture.md`` and
``notes/reference/software-landscape.md``.

Canopy cover
------------

Cover is the share of valid raster cells with canopy height at least 2 m. It is calculated
from the CHM on the source grid, not from a vector crown union. The threshold is a
parameter; a change report must record it.

Canopy volume
-------------

The raster volume is the sum of positive canopy heights times cell area. It is a height
field prism, not a crown hull or a QSM. The tree-level volume is an ellipsoid crown
approximation. The two numbers answer different questions and are labelled separately in
the UI.

Tree records
------------

The UBC inventory is normalised into ``TreeRecord``. Missing height is filled from the CHM
at the tree location when the value is plausible; otherwise from the group allometry.
Missing DBH is estimated from height; missing crown width from DBH. Every imputation is
recorded in the data note, not presented as a measurement.

Growth
------

Annual diameter increment declines toward a species-group asymptote:

.. code-block:: text

   increment = base_rate * (1 - (dbh / max_dbh)^1.5) * competition * climate

Crown light exposure, where recorded, multiplies the increment between 0.75 and 1.10.
Height and crown width follow the group allometry after growth. This is a transparent
scenario model. It is **not** a calibrated i-Tree or FVS projection.

Carbon
------

Above-ground biomass uses the Jenkins et al. (2003) generalized diameter equations, with
the softwood and hardwood coefficients. Carbon is half of above-ground biomass. Roots,
dead wood, and soil carbon are excluded. The UI labels the number as an above-ground
estimate.

Individual-tree detection
-------------------------

The CHM is smoothed only by the local-maximum window. Tree tops are local maxima above a
minimum height; crowns are segmented with a marker-controlled watershed on the inverted
CHM. The result is a first-pass crown map. Dense multi-layer stands, steep terrain, and
overlapping crowns will merge or split. A point-cloud segmentation is future work.

Change
------

Change compares two aligned CHMs at a fixed canopy threshold. It reports gain, loss, stable
canopy, net change, and mean height change on stable canopy. The acquisition date,
leaf-on/leaf-off status, and vertical datum belong in the report. A raw difference is not a
growth rate.

Decision support
----------------

A scenario score combines canopy cover, native share, Shannon diversity, carbon retention,
and a cost penalty. The weights are explicit in ``growth.py``. The score is a conversation
aid, not an objective truth. The planting advisor ranks open, low-canopy cells that are
near existing trees, outside buildings, inside the boundary, and below a slope limit; it
returns the reasons with each candidate.
