Research agenda: shade, optimization, off-inventory canopy, and birds
=====================================================================

Status: P5-P11 are complete. v0.3.0 is released. Updated 2026-11-04.
The detailed plan is
`notes/design/urban-canopy-program-plan.md <https://github.com/UBC-FRESH/fresh-urban-forest-lab/blob/main/notes/design/urban-canopy-program-plan.md>`_
and the evidence review is
`notes/reference/literature-review-shade-optimization-biodiversity.md <https://github.com/UBC-FRESH/fresh-urban-forest-lab/blob/main/notes/reference/literature-review-shade-optimization-biodiversity.md>`_.

Design thesis
-------------

A tree's shade contribution is **marginal**, not absolute. A tree in a closed canopy or in
deep building shade can have a large crown and almost no marginal effect on pedestrian
shade. A spaced street tree can have a smaller crown and a large marginal effect. Canopy
cover cannot distinguish the two.

The programme therefore treats these as first-class, tree-level quantities:

- shaded hours, by season and time of day;
- **marginal shade hours**: additional shade caused by the tree, holding buildings and
  existing trees constant;
- **effective shade**: marginal shade weighted by target importance (pedestrian route,
  plaza, facade, heat-vulnerable population);
- **shade efficiency**: effective shade per unit crown volume, leaf area, water, or cost;
- the site's light and water regime, species fit, growth, vigour, drought stress, and
  irrigation cost.

Every output also carries an **evidence tier**: ``measured``, ``physics``, ``calibrated``,
``scenario``, or ``prior``. A number without a tier is a defect.

What is new, and what is not
----------------------------

The physics is not new. Solar geometry, ray casting, 3D city models, LiDAR individual-tree
detection, allometric growth, NSGA-style optimization, and Pareto visualization are all
established. Recent work explicitly couples 3D trees and buildings for solar and shade
analysis, and local Vancouver work already models canopy shading.

The potential contribution is the **integration and decision semantics**:

1. marginal, time-integrated, building-aware shade as a tree-level decision variable;
2. a coupled light-water-growth-vigour and irrigation-cost layer;
3. a many-objective, spatio-temporal planting optimization;
4. an uncertainty-aware, fuzzy Pareto archive and a linked 3D solution-space viewer;
5. off-inventory/private-canopy trees as a first-class layer with a value-of-information
   test;
6. bird habitat and a prior-driven demographic layer with honest evidence tiers.

Queued phases
-------------

.. list-table::
   :header-rows: 1
   :widths: 8 42 50

   * - Phase
     - Goal
     - Main outputs
   * - P7
     - Solar shade and species-fit engine
     - Shadow kernel, marginal shade, species traits, water/growth/vigour, irrigation cost
   * - P8
     - Spatio-temporal optimization and Pareto explorer
     - Problem schema, parallel solver, fuzzy archive, 3D solution-space UI
   * - P9
     - Off-inventory and private-canopy augmentation
     - Land mask, detection/reconciliation, confidence, value-of-information
   * - P10
     - Bird habitat and demography
     - 3D habitat metrics, relative abundance, prior-driven survival and lambda
   * - P11
     - Integration and v0.3.0 release
     - One scenario/evidence contract, integrated UI, benchmark, docs, release

Recommended order: P7, P8, P9, P10, P11. P9 uses the P8 solver for its value-of-information
experiment; P10 adds an objective to the P8 problem; P11 integrates and releases.

Literature anchors
------------------

Shade and microclimate:

- Meili et al. (2021), *Tree effects on urban microclimate: diurnal, seasonal, and climatic
  temperature differences*, Urban Forestry & Urban Greening,
  https://doi.org/10.1016/j.ufug.2020.126970
- Li et al. (2024), *Cooling efficacy of trees across cities is determined by background
  climate, urban morphology, and tree traits*, Communications Earth & Environment,
  https://doi.org/10.1038/s43247-024-01908-4
- Morakinyo et al. (2017), *A study on the impact of shadow-cast and tree species on
  in-canyon and neighborhood thermal comfort*, Building and Environment,
  https://doi.org/10.1016/j.buildenv.2017.01.005
- Lu et al. (2022), *Modeling the shading effect of Vancouver's urban tree canopy in
  relation to neighborhood variations*, Arboriculture & Urban Forestry,
  https://doi.org/10.48044/jauf.2022.008
- Wang et al. (2025), *Modelling sunlight and shading distribution on 3D trees and
  buildings*, Building and Environment,
  https://doi.org/10.1016/j.buildenv.2025.112816

Species, water, and growth:

- Martin et al. (2016), *Survival is not enough: the effects of microclimate on the growth
  and health of three common urban tree species*, Urban Forestry & Urban Greening,
  https://doi.org/10.1016/j.ufug.2016.06.004
- Rosenberger et al. (2025), *Providing sufficient water for urban trees with limited root
  space during drought*, Urban Forestry & Urban Greening,
  https://doi.org/10.1016/j.ufug.2025.128670
- Tabassum et al. (2023), *Which Plant Where: a plant selection tool for changing urban
  climates*, Arboriculture & Urban Forestry,
  https://doi.org/10.48044/jauf.2023.014

Optimization and visualization:

- Bodnaruk et al. (2017), *Where to plant urban trees? A spatially explicit methodology to
  explore ecosystem service tradeoffs*, Landscape and Urban Planning,
  https://doi.org/10.1016/j.landurbplan.2016.08.016
- Nyelele et al. (2021), *A multi-objective decision support framework to prioritize tree
  planting locations in urban areas*, Landscape and Urban Planning,
  https://doi.org/10.1016/j.landurbplan.2021.104172
- Filipič et al. (2018), *A taxonomy of methods for visualizing Pareto front
  approximations*, GECCO, https://doi.org/10.1145/3205455.3205607

Off-inventory trees:

- Wallace et al. (2021), *Linking urban tree inventories to remote sensing data for
  individual tree mapping*, Urban Forestry & Urban Greening,
  https://doi.org/10.1016/j.ufug.2021.127106
- Klobucar et al. (2021), *Comparing ground and remotely sensed measurements of urban tree
  canopy in private residential property*, Trees, Forests and People,
  https://doi.org/10.1016/j.tfp.2021.100114
- Thomas et al. (2021), *Trees outside forests are an underestimated resource in a country
  with low forest cover*, Scientific Reports, https://doi.org/10.1038/s41598-021-86944-2

Birds:

- Davison et al. (2023), *Vegetation structure from LiDAR explains the local richness of
  birds across Denmark*, Journal of Animal Ecology,
  https://doi.org/10.1111/1365-2656.13945
- Carrasco et al. (2019), *Metrics of lidar-derived 3D vegetation structure reveal
  contrasting effects of horizontal and vertical forest heterogeneity on bird species
  richness*, Remote Sensing, https://doi.org/10.3390/rs11070743
- Lerman et al. (2014), *Using urban forest assessment tools to model bird habitat
  potential*, Landscape and Urban Planning,
  https://doi.org/10.1016/j.landurbplan.2013.10.006

Local grey literature:

- City of Vancouver (2025), *Urban Forest Strategy*,
  https://vancouver.ca/files/cov/2025-urban-forest-strategy.pdf
- UBC News (2026), *New UBC tool helps cities plant trees where they're needed most*
  (CanopyFit),
  https://news.ubc.ca/2026/08/new-tool-helps-cities-plant-trees-where-theyre-needed-most/
- UBC SEEDS (2025), *Modeling Tree Shade Coverage: Planting Recommendations for Optimizing
  Shade at UBC Vancouver*,
  https://sustain.ubc.ca/sites/default/files/seedslibrary/Final%20Report%20Tree%20Planting%20Recommendations%20for%20Optimizing%20Shade%20at%20UBC%20Vancouver_0.pdf

What the programme will not claim
---------------------------------

- It is not a new radiative-transfer or computational-fluid-dynamics model.
- It is not a survey-grade 3D tree reconstruction.
- It is not a calibrated local growth model without repeat measurements.
- It is not a site-specific bird survival estimate without mark-recapture data.
- It is not legal advice on solar access or private-tree regulation.
- "Shadow urban forest" is a nickname, not an established scientific term. The technical
  term is **off-inventory urban trees**; the international framing is **trees outside
  forests (TOF)** where the FAO definition applies.

Why this is worth doing
-----------------------

The programme turns a canopy map into a decision surface: which tree, where, for which
species, under which water policy, for which people and habitats, and with what tradeoffs
and uncertainty. It is also a reproducible benchmark for a question that cities are already
asking: where does a tree actually cool, and who benefits?
