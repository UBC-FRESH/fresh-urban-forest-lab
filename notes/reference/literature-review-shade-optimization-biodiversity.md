# Literature review: shade, species fit, optimization, off-inventory trees, and birds

Status: rapid evidence review, 2026-11-03. This is a planning input, not a systematic review.
It supports the P7-P11 programme plan in
`notes/design/urban-canopy-program-plan.md`.

## Review question

What is already known about:

1. tree and building shade at daily, seasonal, and annual scales;
2. how shade and microclimate affect urban tree species selection, growth, vigour, drought
   stress, and irrigation demand;
3. spatio-temporal multi-objective optimization of urban forests and the visualization of
   high-dimensional Pareto fronts;
4. trees that are missing from official inventories, especially on private land;
5. the relationship between 3D canopy structure and urban bird habitat and demography?

The applied question is whether a tree-level, building-aware, time-integrated shade and
optimization DSS is a genuine research gap or a re-implementation of standard methods.

## Method and limits

- A rapid, purposive review, not a PRISMA systematic review.
- Peer-reviewed papers were found through general web search and Crossref metadata checks.
- Grey literature was included for local policy and tool context: City of Vancouver, UBC,
  Metro Vancouver, USDA Forest Service / i-Tree, and UBC SEEDS.
- Priority was given to papers that explicitly model buildings and trees together, or that
  link canopy structure to a management decision.
- The search was not exhaustive. Citation chaining, a formal screening log, and a
  librarian-assisted search remain P7.1 work.
- Bibliographic details were checked against Crossref where a DOI was available. Grey
  literature URLs were taken from the publisher page; they can change.

## Executive answer

### Are buildings and canopy competition already modelled?

Yes, in separate communities:

- **Microclimate and radiation models** such as SOLWEIG, UMEP, ENVI-met, Radiance, and
  Ladybug resolve buildings, terrain, and trees at hourly or sub-hourly resolution. Recent
  work explicitly couples 3D tree models with building data for solar and shade analysis.
- **Urban forest benefit tools** such as i-Tree use tree size, species, condition, and
  simplified building/energy relationships. They do not run a full 3D daily shadow model
  for every tree.
- **Canopy-cover and shade-provision studies** often use 2D canopy cover, street-view
  greenness, or a single clear-sky shadow snapshot. They rarely compute marginal shade
  against a building-shaded baseline over a full year.
- **Urban forest optimization studies** usually optimize planting locations against
  ecosystem-service proxies, land use, or canopy cover. Few optimize time-integrated,
  building-aware shade together with species water demand and growth.

So the user's intuition is substantially right: a tree in a closed canopy or in deep
building shade often has a **low marginal contribution to pedestrian shade**, even though it
still contributes to canopy cover, evapotranspiration, carbon, and habitat. Most
canopy-cover metrics cannot see this difference.

### Is that a literature contribution?

The physics and the individual methods are not new. The **integration and decision
semantics** are potentially new:

1. treat **marginal, time-integrated, effective shade** as a tree-level decision variable,
   not canopy cover;
2. separate **building shade, existing-canopy shade, and new-tree shade** at the same
   space and time;
3. couple that shade field to **species light/water/growth/vigour** and **irrigation cost**;
4. use it inside a **many-objective, spatio-temporal planting optimization**;
5. include **off-inventory trees** and **bird habitat** as first-class objectives;
6. show the resulting **fuzzy Pareto front** in an interactive 3D solution-space viewer.

That is a credible applied contribution and a strong open-software paper. It should be
framed as an integration contribution, not as a new law of radiative transfer. A formal
novelty claim needs the P7.1 systematic review and a benchmark against at least one
existing tool.

## Evidence map

| Theme | What is established | What is weak or missing | Relevance |
| --- | --- | --- | --- |
| Solar geometry and shadow casting | Mature; NOAA/SPA, Radiance, SOLWEIG, CityGML workflows | City-scale, tree-level, daily/seasonal analytics with management decisions | P7.2 |
| Tree and building shade | Buildings can dominate shade in dense canyons; trees dominate in open streets; effects vary by season and time of day | Marginal shade of an individual tree against a building-shaded baseline | P7.3 |
| Shade and thermal comfort | Shade reduces mean radiant temperature and heat stress; tree species and crown traits matter | Tree-level DSS that reports shade-hours and uncertainty, not only temperature snapshots | P7.3, P7.7 |
| Species selection | Light demand, drought tolerance, soil volume, heat, and water use are established traits | Trait data for BC species and a transparent site-match model | P7.4 |
| Growth, vigour, drought | Urban microclimate and water availability affect growth and survival; building shade can reduce light and water demand | Coupled light-water-growth model at tree level; repeat-measure calibration | P7.5 |
| Irrigation | Soil water balance and species coefficients are standard; limited root space changes the policy | Cost per shade-hour and a policy simulator linked to species/site | P7.6 |
| Multi-objective planting | Spatial optimization and Pareto methods are mature | Time-integrated shade, water, habitat, and uncertainty in one problem | P8 |
| Pareto visualization | Many methods exist: scatter matrices, parallel coordinates, radial plots, 3D projections | Linked 3D slices through a fuzzy n-D front for urban-forest decisions | P8.5 |
| Off-inventory trees | Trees outside forests and private residential canopy are recognised; LiDAR ITD is mature | Operational reconciliation with official inventory and value-of-information | P9 |
| Bird habitat | LiDAR structure predicts bird richness and composition; canopy cover predicts abundance | Tree-level scenario linkage and demographic survival with local data | P10 |

## 1. Shade, buildings, and microclimate

Meili et al. (2021) show that tree effects on urban microclimate are diurnal and seasonal:
shade dominates daytime cooling, while at night trees can reduce sky-view and trap
longwave radiation. A single daytime snapshot is therefore not a shade assessment.

Li et al. (2024) find that cooling efficacy depends on background climate, urban
morphology, and tree traits. The same tree does not deliver the same cooling in a
low-rise street, a dense canyon, or a park. This supports a site-specific model.

Morakinyo et al. (2017) show that shadow-cast and tree species both change in-canyon
thermal comfort. The effect is not just "tree present or absent"; crown form and placement
matter.

Armson et al. (2013) compare the shading effectiveness of five street tree species and
show large differences in the shade cast per tree. Li et al. (2018) quantify street-tree
shade provision in Boston from street-view imagery, but the method is a snapshot and does
not resolve the full daily/seasonal shadow or the building-shaded baseline.

Lu et al. (2022) build a 3D canopy and building model for Vancouver with ALS and a
Radiance-based simulation. This is the closest local precedent: it shows that tree canopy
shading varies by neighbourhood and building morphology. It is a neighbourhood/roof and
facade assessment, not a tree-level planting optimizer.

Recent 3D work closes the geometry gap:

- Wang et al. (2025) model sunlight and shading on 3D trees and buildings with a
  deep-learning-augmented geospatial framework.
- Shirinyan et al. (2025) perform district-scale 3D solar analysis and note that 3D city
  models often lack high vegetation.
- A 2026 ISPRS citywide assessment explicitly adds semantic 3D tree models to CityGML and
  models roof and facade irradiation with and without tree shade.
- Gai et al. (2025) compare shade infrastructure, including buildings and trees, and report
  large PET reductions from building shade in hot-humid summers.
- Son et al. (2026) find that building shade is more effective in densely built areas,
  while tree shade gives more stable conditions near parks.

**Conclusion:** building-aware shade physics is established. What is uncommon is using
**marginal tree shade** at tree level, over a full year, as the signal that drives species
choice, water policy, and planting optimization.

## 2. Species selection, growth, vigour, drought, and water

Martin et al. (2016) show that survival is not enough: microclimate affects growth and
health of common urban species in San Francisco. A species that survives can still perform
poorly.

Esperon-Rodriguez et al. (2025) synthesise urban tree growth and drought responses and
report context-dependent effects, including positive growth under some hot conditions.
This is a warning against a single "drought tolerance" score: site, water, and species
interact.

Rosenberger et al. (2025) show that limited root space changes irrigation needs; weekly
irrigation can fail to avoid drought stress, while daily irrigation reduces sensitivity.
This is directly relevant to street trees in small soil volumes.

Symes and Connellan (2013) and Schuch et al. (2018) document irrigation strategies and
water requirements in dry urban environments. Nouri et al. (2013) review
evapotranspiration measurement for urban landscape vegetation. The standard building
blocks exist: reference evapotranspiration, crop coefficients, soil water storage, and
irrigation efficiency. The gap is linking them to a specific tree, its shade regime, and a
costed policy.

Species-selection tools already exist:

- Tabassum et al. (2023), *Which Plant Where*, selects species for changing urban climates.
- Prasad et al. (2016) combine habitat suitability, colonisation, and knowledge-based
  models for climate-change species management.
- The Metro Vancouver Tree Guide and the City of Vancouver strategy provide local
  species and policy context.

**Conclusion:** a species trait table and a daily water balance are not novel. A coupled
light-water-growth-vigour model that uses the **local shade regime** and reports
**uncertainty and cost** is the useful integration.

## 3. Spatio-temporal optimization and Pareto visualization

Spatial optimization for urban tree planting is established:

- Bodnaruk et al. (2017) explore priority planting and ecosystem-service tradeoffs in
  Baltimore with a spatially explicit method.
- Nyelele et al. (2021) build a multi-objective decision-support framework for planting
  locations.
- Wicki et al. (2021) use participatory multi-objective optimization for dense and green
  cities.
- Elliot et al. (2019) combine participatory and multi-objective integer linear programming
  for urban ecosystem services.
- Marques et al. (2021) build Pareto frontiers for forest ecosystem-service tradeoffs.
- Dong et al. (2026) optimize urban tree species composition for nature-based solutions.

These are mostly **spatial** and often **single-period**. They rarely combine daily shade,
tree growth, water demand, off-inventory canopy, and bird habitat over a multi-decade
horizon.

High-dimensional Pareto visualization is also mature:

- Filipič et al. (2018) taxonomise Pareto-front visualization methods.
- Ibrahim et al. (2016) present 3D-RadVis for many-objective fronts.
- Tušar and Filipič (2014) treat visualization as its own many-objective problem.

**Conclusion:** NSGA-style search and Pareto plots are standard. The contribution would be
the **problem formulation** (time-integrated marginal shade and coupled services), the
**uncertainty-aware archive**, and the **linked 3D slice UI** for decision-makers. The
"orbit mouse" viewer is a UX contribution, not a new optimization algorithm.

## 4. Off-inventory and private urban trees

The literature has several relevant terms:

- **Trees outside forests (TOF)**: FAO and national-inventory framing for trees not in
  classified forest. Thomas et al. (2021) show TOF can be an underestimated resource.
- **Private residential canopy**: Klobucar et al. (2021) compare ground and remotely sensed
  canopy measurements on private residential property and show both error and value.
- **Off-inventory** or **unmapped** trees: descriptive terms for trees missing from a
  municipal or campus inventory.
- **Urban tree inventory methods**: Nielsen et al. (2014) review single-tree inventory
  methods; Wallace et al. (2021) link existing inventories to LiDAR individual-tree
  detection; Zhang et al. (2015) segment individual trees from LiDAR for urban inventory.

"Shadow urban forest" is **not** an established technical term. In real estate, "shadow
inventory" means unsold or off-market housing. It should not be used as a scientific term.
Recommended language:

- **off-inventory urban trees** for the operational layer;
- **private-property canopy** when ownership is the point;
- **trees outside formal inventory** for a policy audience;
- **trees outside forests (TOF)** only when using the FAO/forest-inventory definition.

A large share of urban canopy is on private land. The exact share is city-specific; the
City of Vancouver strategy and local canopy assessments are the right source for a
Vancouver number, not a generic global percentage.

The value-of-information question is: does adding an imperfect off-inventory layer change
the recommended plan, the predicted shade, the habitat score, or the equity outcome enough
to justify the cost? That is testable. The "almost-zero cost" claim should be stated as
**low marginal cost given an existing LiDAR acquisition**, not zero cost.

## 5. Birds, canopy structure, and demography

LiDAR structure predicts bird richness and composition:

- Davison et al. (2023) show that LiDAR-derived vegetation structure explains local bird
  richness across Denmark, and is as important as habitat availability.
- Carrasco et al. (2019) find contrasting effects of horizontal and vertical heterogeneity
  on bird species richness.
- Lerman et al. (2014) integrate bird habitat suitability into urban forest assessment
  tools; Lerman et al. (2026) revisit this for i-Tree-style ecosystem-service assessment.

Canopy cover and native tree origin also matter:

- A 2025 study finds canopy cover is a strong predictor of some urban bird abundances.
- Basile et al. (2025) find that the benefit of urban trees for birds depends on how much
  native species contribute to canopy cover.

Demography is the weak link. Bird density or richness is not a survival rate, and eBird
relative abundance is not a population density. A credible `lambda` (population growth
rate) and survival curve need mark-recapture, nest monitoring, or a formal integrated
population model. The plan should use:

- eBird or local point counts for **relative abundance**;
- literature survival priors for a **stage-structured** model;
- local mark-recapture only if a partner provides it;
- explicit uncertainty and sensitivity, not a single "bird score".

**Conclusion:** a bird habitat layer is feasible with existing data. A bird demographic
claim requires new field data and an ecology collaborator. The prototype can build the
scenario linkage and the evidence contract, and label the demographic output as a
prior-driven exploration until validated.

## 6. Local Vancouver and UBC grey literature

- City of Vancouver (2025), *Urban Forest Strategy*: about 25% canopy cover and a 30% by
  2050 target; explicit equity and climate-adaptation framing.
- UBC News (2026), *CanopyFit*: a UBC tool that maps physical barriers, heat, and equity to
  prioritize tree planting for shade and cooling. This is the closest local decision-support
  precedent and should be treated as a collaborator/benchmark, not a competitor to copy.
- UBC SEEDS (2025), *Modeling Tree Shade Coverage: Planting Recommendations for Optimizing
  Shade at UBC Vancouver*: a campus shade-optimization study; useful local baseline and
  data source.
- Lu et al. (2022): Vancouver 3D canopy/building shading with ALS and Radiance.
- Czekajlo et al. (2023): four neighbourhood-scale 2050 urban-forest scenarios for
  Vancouver; links canopy scenarios to building cooling demand.
- Metro Vancouver, *Climate 2050: Nature and Ecosystems Roadmap*: regional adaptation and
  urban-forest policy context.
- USDA Forest Service, *i-Tree* methods and tools: a benchmark for benefit transfer; not a
  full 3D shade engine.
- FAO, *Trees Outside Forests*: terminology and inventory framing for off-inventory trees.

**Positioning:** CanopyFit and the UBC SEEDS work already cover planting prioritization and
shade mapping. This project should not duplicate a static shade-priority map. It should add
the **tree-level, time-integrated, building-aware, species/water/optimization** layer and
the **open reproducible lab**.

## Novelty assessment

| Element | State of the art | This project | Novelty |
| --- | --- | --- | --- |
| Solar position and ray casting | Mature | Reuse NOAA/SPA and a tested shadow kernel | None |
| 3D building + tree shade | Active research; Radiance, SOLWEIG, CityGML | Same physics, but tree-level and daily/seasonal | Low |
| Shade metric | Canopy cover, shade provision snapshots | Marginal effective shade-hours, building-aware | **Medium** |
| Species selection | Trait tools and climate matching | Trait fit driven by local light/water regime | Medium |
| Growth/vigour | Allometry and microclimate studies | Coupled light-water-growth with uncertainty | Medium |
| Irrigation | Soil water balance and species coefficients | Costed policy linked to shade and species | Medium |
| Optimization | Spatial multi-objective planting | Time-integrated shade + water + habitat + birds | **Medium-high** |
| Pareto UI | Many visualization methods | Linked 3D slices through a fuzzy n-D archive | Medium |
| Off-inventory trees | TOF, private canopy, LiDAR ITD | Reconciliation + value-of-information | **Medium-high** |
| Bird habitat | LiDAR structure and richness | Tree-level scenario linkage; demographic tier | Medium |
| Open software | Many tools, few integrated | Reproducible MIT lab | Medium |

The strongest publishable claims are:

1. **Marginal shade accounting**: a tree's shade contribution is conditional on what is
   already shaded by buildings and other trees. This changes species and site rankings.
2. **Shade-aware species fit**: the same species is a different choice in a sunlit street,
   a building-shaded canyon, and a closed canopy.
3. **Value of off-inventory canopy**: an imperfect LiDAR-derived private/off-inventory layer
   can change the optimal plan and the equity outcome; quantify when it is worth it.
4. **Fuzzy Pareto decision space**: show the shape, tradeoffs, and uncertainty of the
   solution space, not a single "best" plan.
5. **Open benchmark**: a reproducible Vancouver/UBC case with public data, code, and
   evidence tiers.

## Candidate papers and outputs

- **Methods / integration paper**: "Marginal shade accounting for urban forest decisions:
  coupling building shade, species water demand, and multi-objective planting."
- **Applied case study**: "Where does an urban tree actually cool? A tree-level shade and
  irrigation optimization for a Vancouver campus."
- **Remote sensing / urban forestry**: "Off-inventory urban trees: reconciling LiDAR
  individual-tree detection with a municipal inventory and valuing the missing canopy."
- **Optimization / visualization**: "A fuzzy Pareto explorer for spatio-temporal urban
  forest planning."
- **Ecology**: "Canopy structure, bird habitat, and demographic uncertainty in urban forest
  scenarios" (only with an ecology partner and field data).
- **Software**: "FRESH Urban Forest Lab: an open, evidence-tiered decision-support lab for
  urban canopy, shade, water, and habitat."

## What not to claim

- Do not claim a new radiative-transfer model.
- Do not claim that a detected crown is a verified tree.
- Do not claim that a prior-driven bird lambda is a local population estimate.
- Do not claim that a canopy-cover change is a shade change.
- Do not claim that a generic growth curve is a calibrated local growth model.
- Do not claim that "shadow urban forest" is an established term.

## Next evidence work (P7.1)

- Write a search protocol and screening log.
- Citation-chain the 2024-2026 3D tree/building shade papers.
- Check SOLWEIG, UMEP, Radiance, CitySim, and i-Tree for what they actually model.
- Search specifically for "marginal shade", "shade provision", "shade equity", and
  "effective shade" metrics.
- Search for urban forest optimization papers that include building shade or water demand.
- Search for off-inventory/private-canopy value-of-information studies.
- Search for urban bird demographic models linked to canopy scenarios.
- Ask a UBC librarian to review the search strategy before the novelty claim is frozen.

## Search log (summary)

Search themes included: urban tree shade building shadow microclimate; species selection
drought irrigation; multi-objective urban forest optimization; Pareto front visualization;
LiDAR bird habitat; private/off-inventory trees; 3D city model solar shading; Vancouver and
UBC urban forest policy. Crossref was used to confirm DOI, year, and container for the
peer-reviewed entries. This was a rapid review, not a reproducible systematic search.
