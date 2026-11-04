# Programme plan: shade, species fit, optimization, off-inventory canopy, and birds

Status: proposed programme plan, 2026-11-03.
Related literature review:
`notes/reference/literature-review-shade-optimization-biodiversity.md`.
Related roadmap phases: P7, P8, P9, P10, P11.
This note is planning only. No phase is active and no implementation task has started.

## 1. Why this programme

The current prototype answers three questions well: what canopy is present, how has it
changed between acquisitions, and what would a simple planting/removal scenario do. It does
not answer the harder planning questions:

- Where does a tree's shade actually land, at what time of day and year, and how much of
  that shade is new rather than shade a building or another tree already provides?
- Which species will grow, stay vigorous, and avoid drought stress in that specific light
  and water regime?
- What irrigation policy does that imply, and what does it cost per unit of effective shade?
- If we optimize planting across space and time, what does the tradeoff space look like, and
  how uncertain is the front?
- What canopy is missing from the official inventory, and does including it change the
  decision?
- Does the plan support birds, or only canopy cover?

The programme adds a **shade-and-species decision layer** and a **multi-objective solution
explorer** on top of the existing dataset, scenario, and 2D/3D stack.

## 2. Design thesis

**A tree's shade contribution is marginal, not absolute.** A tree in a closed canopy or in
deep building shade can have a large crown and almost no marginal effect on pedestrian
shade. A spaced street tree can have a smaller crown and a large marginal effect. Current
canopy-cover metrics cannot distinguish the two.

The programme therefore treats the following as first-class, tree-level quantities:

- `shade_hours`: time a target surface is shaded, by season and time of day;
- `marginal_shade_hours`: additional shade caused by the tree, holding buildings and other
  trees constant;
- `effective_shade_hours`: marginal shade weighted by target importance (pedestrian route,
  plaza, facade, vulnerable population);
- `shade_efficiency`: effective shade per unit crown volume, leaf area, water, or cost;
- `light_regime` and `water_regime`: the site conditions the tree actually experiences;
- `species_fit`, `growth`, `vigour`, `drought_stress_days`, `irrigation_need`, and
  `irrigation_cost`;
- `habitat_value` and `bird_relative_abundance` for the resulting structure.

**Evidence tier travels with every number.** Each output names its method and one of:

- `measured`: field or inventory measurement;
- `physics`: deterministic geometry/radiation calculation;
- `calibrated`: fitted to local observations with diagnostics;
- `scenario`: model projection under stated assumptions;
- `prior`: literature or expert prior, not locally validated.

The UI and exports must show the tier. A number without a tier is a bug.

## 3. Scope

In scope:

- solar geometry, terrain/building/tree shadow, daily/seasonal/annual aggregation;
- tree-level marginal shade and shade equity on chosen target surfaces;
- species traits and site fit for light, water, soil, heat, and space;
- coupled light-water-growth-vigour model with uncertainty;
- irrigation policy and cost simulation;
- many-objective, spatio-temporal planting/removal/irrigation optimization;
- fuzzy Pareto archive and interactive 3D solution-space exploration;
- off-inventory/private-canopy detection, reconciliation, and value of information;
- bird habitat metrics, relative abundance, and prior-driven demographic projection;
- open data contracts, CLI, API, docs, tests, and benchmark.

Out of scope for this programme:

- a new radiative-transfer or computational-fluid-dynamics model;
- a survey-grade 3D tree reconstruction or quantitative structure model;
- a calibrated local growth model without repeat measurements;
- a site-specific bird survival estimate without mark-recapture data;
- legal advice on private-tree regulation, solar access, or liability;
- a multi-tenant production service with accounts and roles;
- an i-Tree replacement claim.

## 4. Relationship to the current system

The existing contracts stay. The programme adds modules and a schema version rather than a
rewrite.

```text
existing dataset
  + solar and shade layer
  + species/water/growth layer
  + optimization and Pareto layer
  + off-inventory layer
  + bird habitat/demography layer
  -> one scenario/evidence contract
  -> 2D map + 3D scene + Light/Species/Water/Optimize/Birds surfaces
```

The core remains standalone and MIT. Optional extras may use permissively licensed
libraries, but no copyleft code is copied. `pymoo`, `scikit-learn`, `pvlib`, `eBird`, and
similar tools are optional adapters or data sources, not core imports.

## 5. Architecture

### 5.1 New modules

| Module | Responsibility |
| --- | --- |
| `solar.py` | Solar vector, sunrise/sunset, clear-sky irradiance, time grid, TMY weighting |
| `shadow.py` | Terrain/building/tree shadow raster and facade sampling; z-buffer or ray casting |
| `shade.py` | Shade-hours, marginal shade, effective shade, shade equity, efficiency |
| `species.py` | Species trait table and site-fit scoring |
| `water.py` | Daily soil-water balance, ET, irrigation, runoff, stress days |
| `vigor.py` | Light/water/heat/soil growth modifiers and vigour score |
| `irrigation.py` | Policy templates, water volume, cost, cost per shade-hour |
| `optimize.py` | Problem schema, decision variables, constraints, objective evaluator |
| `pareto.py` | Non-dominated archive, hypervolume, fuzzy dominance, slice extraction |
| `surrogate.py` | Design of experiments, emulator training, validation |
| `jobs.py` | Process-pool execution, checkpoints, resume, progress events |
| `off_inventory.py` | Land/ownership proxy, ITD reconciliation, confidence, value of information |
| `habitat.py` | 3D canopy/habitat metrics and bird relative-abundance model |
| `demography.py` | Stage-structured projection, survival curve, lambda, sensitivity |
| `evidence.py` | Evidence tier, method label, uncertainty interval, provenance helpers |

### 5.2 Contract extensions

Add frozen dataclasses with JSON round-trip helpers:

- `SolarTimeGrid`: timezone, date range, time step, representative days.
- `ShadeTarget`: surface type, geometry, weight, population/heat weight.
- `ShadeResult`: shaded hours, marginal hours, effective hours, by season and target.
- `SpeciesProfile`: light demand, drought tolerance, water-use coefficient, soil volume,
  mature size, growth rate, native flag, salt/heat/flood tolerance, allergen/BVOC flags.
- `SiteConditions`: light regime, soil volume, land cover, ownership class, irrigation.
- `WaterBalance`: daily soil moisture, ET, irrigation, runoff, stress days.
- `SpeciesFit`: trait match, limiting factors, confidence.
- `GrowthProjection`: DBH/height/crown by year, modifiers, uncertainty, evidence tier.
- `IrrigationPolicy`: schedule, annual volume, cost, cost per shade-hour.
- `OptimizationProblem`: variables, objectives, constraints, horizon, seeds.
- `Solution`: decision vector, objective vector, metrics, constraint violation, scenario id.
- `ParetoArchive`: solutions, dominance, uncertainty, hypervolume, slice metadata.
- `OffInventoryTree`: geometry, height, crown, confidence, land class, match status.
- `BirdHabitat`: structure metrics, suitability, relative abundance, uncertainty.
- `DemographicProjection`: stage vector, survival curve, lambda, sensitivity.

`DatasetManifest` moves to `fresh-urban-forest.dataset.v2`. The migration adds model
versions, evidence tiers, and optional layers. The loader accepts v1 and writes v2.

### 5.3 Service and CLI

New API groups:

- `/api/shade` and `/api/shade.png`
- `/api/species/fit`
- `/api/water`
- `/api/irrigation`
- `/api/optimize` and `/api/optimize/{job}`
- `/api/optimize/{job}/solutions`
- `/api/off-inventory`
- `/api/birds`

New CLI commands:

```text
fresh-urban-forest shade --dataset ... --date ... --times ... --out ...
fresh-urban-forest species-fit --dataset ... --species ... --out ...
fresh-urban-forest water --dataset ... --climate ... --out ...
fresh-urban-forest optimize --problem ... --workers ... --out ...
fresh-urban-forest pareto --archive ... --slices ... --out ...
fresh-urban-forest off-inventory --dataset ... --parcels ... --out ...
fresh-urban-forest birds --dataset ... --observations ... --out ...
```

Long jobs return a job id and stream progress as server-sent events. Every job writes a
manifest with code version, data hashes, seeds, and command line.

### 5.4 UI

- **Light** tab: date, time, play-day, season, full-year average; 3D sun position; shadow
  map; building-only/tree-only/combined toggle; target-surface selector.
- **Tree shade card**: marginal shade, building-shaded fraction, shade efficiency, best
  season, target hit map.
- **Species** panel: trait match, limiting factor, growth range, vigour, drought risk,
  irrigation need, cost range.
- **Water** panel: soil moisture, stress days, irrigation schedule, annual cost, cost per
  shaded hour.
- **Optimize** tab: objectives, constraints, budget, horizon, workers, run/resume; solution
  count, hypervolume, convergence.
- **Solution space**: 3D point cloud with orbit controls, axis selectors, colour/size by
  objective, slice plane, 2D projections, parallel coordinates, hover/select/load scenario.
- **Birds** tab: habitat metrics, relative abundance, survival curve, lambda with credible
  interval, sensitivity.
- **Evidence badge** on every card: method, tier, uncertainty, and source.

The browser must stay offline-capable. The 3D solution viewer uses vendored Three.js and
instanced buffers, not a new external service.

## 6. Phase plan

The phases are sequential by default. P8 can begin after P7.2-P7.4 are stable. P9 uses the
P8 solver for its value-of-information experiment. P10 adds an objective to the P8 problem.
P11 integrates and releases.

### Phase 7: Solar shade and species-fit engine

Parent issue: P7 (queued).
Branch: `feature/p7-shade-species`.
Goal: turn solar geometry and 3D obstruction into tree-level marginal shade, then connect
that shade regime to species fit, growth, vigour, drought stress, and irrigation cost.

P7.1 Evidence review and method lock
- [ ] Write the search protocol, screening log, and citation-chain plan.
- [ ] Compare SOLWEIG, UMEP, Radiance, CitySim, Ladybug, and i-Tree capabilities.
- [ ] Freeze the novelty claim and the benchmark target.
- [ ] Record the decision in an ADR.

P7.2 Solar geometry and shadow kernel
- [ ] Implement NOAA/SPA solar vector, sunrise/sunset, and time grid.
- [ ] Implement terrain horizon, building extrusion, and tree-crown shadow.
- [ ] Support ground (1.5 m), facade, roof, and custom target sampling.
- [ ] Use representative days plus optional full-year mode.
- [ ] Validate against NOAA/SPA, analytic shapes, and a small Radiance/SOLWEIG scene.

P7.3 Shade accounting and marginal contribution
- [ ] Compute shaded hours, marginal tree shade, building shade, and canopy competition.
- [ ] Compute effective shade on weighted target surfaces.
- [ ] Compute shade efficiency per crown volume, leaf area, water, and cost.
- [ ] Detect "shade deserts" and over-shaded planting sites.
- [ ] Report seasonal and annual aggregates with uncertainty.

P7.4 Species traits and site fit
- [ ] Build a BC/Vancouver species trait table with sources and confidence.
- [ ] Score light, water, soil volume, heat, salt, space, and mature-size fit.
- [ ] Return limiting factors and a ranked species list.
- [ ] Keep native, allergen, BVOC, and pest flags separate from the fit score.

P7.5 Coupled light-water-growth-vigour model
- [ ] Implement daily soil-water balance and ET.
- [ ] Implement light, water, heat, soil, and competition modifiers.
- [ ] Project DBH, height, crown, and vigour with uncertainty bands.
- [ ] Calibrate where local data allow; otherwise label as scenario/prior.
- [ ] Compare against the existing generic growth model.

P7.6 Irrigation policy and cost
- [ ] Implement none, establishment, fixed, soil-moisture-triggered, and deficit policies.
- [ ] Compute water volume, runoff, labour, and annual cost.
- [ ] Compute cost per effective shade-hour and cost per stress-day avoided.
- [ ] Report a range, not a single mandate.

P7.7 Shade and species UI
- [ ] Add the Light tab, sun dial, time/date/season controls, and shadow layers.
- [ ] Add the tree shade card, species panel, water panel, and evidence badges.
- [ ] Add a compare mode: building-only vs building+trees.
- [ ] Keep the 2D and 3D selection shared.

P7.8 Validation, uncertainty, and report
- [ ] Test solar position, shadow geometry, and time integration.
- [ ] Run a field/orthophoto shadow check on a small campus scene.
- [ ] Run sensitivity to grid, time step, crown shape, and transmissivity.
- [ ] Write `notes/reports/p7-shade-species.md` with limits.

Acceptance criteria:

- A date/time request returns a georeferenced shadow raster and shade metrics.
- A full-year aggregate returns seasonal and annual shade-hours with uncertainty.
- A tree shade card separates building shade, canopy shade, and marginal tree shade.
- A species list is ranked by site fit with limiting factors and evidence tiers.
- A water/irrigation card gives stress days and a cost range.
- The dashboard is green and the docs describe the method and limits.

Verification:

```bash
python scripts/dashboard.py
fresh-urban-forest shade --dataset data/demo/ubc_core --date 2026-06-21 --times 08:00,12:00,16:00 --out tmp/shade
fresh-urban-forest species-fit --dataset data/demo/ubc_core --species "Acer rubrum" --out tmp/fit.json
```

### Phase 8: Spatio-temporal optimization and Pareto explorer

Parent issue: P8 (queued).
Branch: `feature/p8-optimize-pareto`.
Goal: solve many planting/removal/irrigation/species allocation problems over a multi-decade
horizon, compile a fuzzy Pareto archive, and explore it as an interactive 3D solution space.

P8.1 Decision model and objective schema
- [ ] Define site/species/year/irrigation variables and removal/replacement options.
- [ ] Define objectives: effective shade, shade equity, native share, diversity, carbon,
  habitat, cost, water, maintenance, and building-energy proxy.
- [ ] Define constraints: budget, spacing, soil, building clearance, species mix, water.
- [ ] Add a machine-readable problem schema and examples.

P8.2 Fast evaluator and surrogate
- [ ] Build a fast analytical evaluator for shade, growth, water, and habitat.
- [ ] Add design of experiments and an emulator for expensive evaluations.
- [ ] Validate the emulator against the full model on a holdout.
- [ ] Record surrogate error in every solution.

P8.3 Parallel solver and job orchestration
- [ ] Implement deterministic seeds and a process-pool runner.
- [ ] Add checkpoint/resume and per-chunk manifests.
- [ ] Decompose by neighbourhood/window and merge archives.
- [ ] Add progress events and cancellation.
- [ ] Benchmark scaling on 1, 4, 8, and 16 workers.

P8.4 Pareto archive and fuzzy dominance
- [ ] Implement non-dominated filtering and archive merging.
- [ ] Compute hypervolume and convergence diagnostics.
- [ ] Add bootstrap/ensemble uncertainty and dominance probability.
- [ ] Distinguish possible, robust, and consensus Pareto sets.
- [ ] Add slice extraction for any three objectives.

P8.5 3D solution-space explorer
- [ ] Render the archive as an instanced point cloud with orbit controls.
- [ ] Add axis selectors, colour/size/opacity by objective, and a slice plane.
- [ ] Add linked 2D projections, parallel coordinates, and brushing.
- [ ] Add hover, select, compare, and "load as scenario".
- [ ] Show projection loss and uncertainty, not just a pretty cloud.

P8.6 Benchmark, sensitivity, and report
- [ ] Build a toy problem with a known front.
- [ ] Compare NSGA-II/III or an in-house solver on hypervolume and runtime.
- [ ] Test constraint satisfaction, determinism, and restart.
- [ ] Write `notes/reports/p8-optimization-pareto.md`.

Acceptance criteria:

- A 100-site, 5-species, 20-year problem with at least four objectives solves end to end.
- The archive is non-dominated, reproducible from a seed, and carries uncertainty.
- The UI can orbit, slice, brush, and load a solution as a scenario.
- The benchmark reports hypervolume, runtime, and surrogate error.
- The dashboard is green.

Verification:

```bash
python scripts/dashboard.py
fresh-urban-forest optimize --problem data/demo/ubc_core/optimization_example.json --workers 8 --out tmp/optimize
fresh-urban-forest pareto --archive tmp/optimize/archive.json --slices 3 --out tmp/pareto
```

### Phase 9: Off-inventory and private-canopy augmentation

Parent issue: P9 (queued).
Branch: `feature/p9-off-inventory`.
Goal: detect and reconcile trees missing from the official inventory, estimate the value of
including them, and keep private-property data safe.

P9.1 Terminology, privacy, and data governance
- [ ] Adopt "off-inventory urban trees" as the technical term.
- [ ] Record that "shadow urban forest" is a nickname, not a literature term.
- [ ] Define the privacy rule: no owner names, addresses, or private photos in tracked data.
- [ ] Record parcel and LiDAR licences and redistribution limits.

P9.2 Land mask and ownership proxy
- [ ] Acquire parcel/right-of-way/park/building layers where available.
- [ ] Build public/private/unknown land classes.
- [ ] Record the confidence and legal limits of the proxy.
- [ ] Test on UBC and a City of Vancouver pilot area.

P9.3 Off-inventory detection and attribution
- [ ] Run ITD on LiDAR/imagery and match to the official inventory.
- [ ] Classify unmatched crowns as off-inventory candidate, missed public tree, or false positive.
- [ ] Estimate height, crown, species probability, and condition proxy.
- [ ] Attach a confidence score and evidence tier.
- [ ] Validate on a permitted field sample.

P9.4 Inventory reconciliation and update workflow
- [ ] Produce a match/mismatch report and a review queue.
- [ ] Add stable ids and duplicate suppression.
- [ ] Define an annual/2-year refresh workflow.
- [ ] Keep the official and augmented layers separate and joinable.

P9.5 Value-of-information experiment
- [ ] Run the P8 optimizer with official-only and augmented populations.
- [ ] Compare selected plans, shade, equity, habitat, and cost.
- [ ] Estimate decision-regret and the value of the added layer.
- [ ] Report when the imperfect layer is worth using and when it is not.

P9.6 UI, confidence layer, and report
- [ ] Add an off-inventory layer with confidence and land class.
- [ ] Add a toggle and a data-quality panel.
- [ ] Add an aggregate-only public view.
- [ ] Write `notes/reports/p9-off-inventory.md`.

Acceptance criteria:

- An off-inventory layer exists for the pilot with confidence and land class.
- Reconciliation separates unmatched, missed, and false-positive cases.
- A value-of-information experiment reports whether the plan changes.
- No private owner data is tracked or exposed.
- The dashboard is green.

Verification:

```bash
python scripts/dashboard.py
fresh-urban-forest off-inventory --dataset data/processed/ubc_lidar_2021 --parcels data/raw/parcels --out tmp/off_inventory
```

### Phase 10: Bird habitat and demography

Parent issue: P10 (queued).
Branch: `feature/p10-birds`.
Goal: connect 3D canopy structure and management scenarios to bird habitat, relative
abundance, and a prior-driven demographic projection with explicit uncertainty.

P10.1 Bird data and evidence tier
- [ ] Acquire eBird or local point-count data under its terms.
- [ ] Define guilds and the species scope.
- [ ] Decide what is relative abundance versus density versus survival.
- [ ] Record the evidence tier for every bird output.

P10.2 3D habitat metrics
- [ ] Compute canopy height, vertical complexity, foliage height diversity, gaps, layering,
  native share, size diversity, and 3D connectivity.
- [ ] Add building collision and human-disturbance proxies where data allow.
- [ ] Aggregate per tree, stand, and neighbourhood.

P10.3 Habitat and relative-abundance model
- [ ] Fit a habitat suitability / relative-abundance model with holdout validation.
- [ ] Report variable importance and uncertainty.
- [ ] Avoid claiming density from relative indices.

P10.4 Demographic layer and lambda
- [ ] Build a stage-structured projection with literature survival/fecundity priors.
- [ ] Produce survival curves and lambda with credible intervals.
- [ ] Run sensitivity/elasticity.
- [ ] Label as prior-driven until local mark-recapture exists.

P10.5 Scenario UI and reporting
- [ ] Add a Birds tab with habitat, abundance, survival, and lambda cards.
- [ ] Link bird metrics to the scenario timeline.
- [ ] Add uncertainty bands and a "what would change this" panel.

P10.6 Validation and expert review
- [ ] Hold out observations and report predictive performance.
- [ ] Ask a UBC bird ecologist to review the model and claims.
- [ ] Write `notes/reports/p10-birds.md` with limits.

Acceptance criteria:

- A scenario returns habitat metrics and relative abundance with uncertainty.
- A demographic projection returns survival curves and lambda with intervals.
- The UI labels the evidence tier and does not imply site-specific survival.
- An expert review is recorded.
- The dashboard is green.

Verification:

```bash
python scripts/dashboard.py
fresh-urban-forest birds --dataset data/demo/ubc_core --observations data/raw/ebird.csv --out tmp/birds
```

### Phase 11: Integration and v0.3.0 release

Parent issue: #44 (closed).
Branch: `feature/p11-integration`.
Goal: make the new layers one coherent lab, document them, benchmark them, and release
v0.3.0.

Status: historical plan. Completion evidence is in ``ROADMAP.md`` and
``notes/reports/p11-integration.md``.

P11.1 Unified scenario and evidence contract
- [ ] One scenario reports shade, water, cost, biodiversity, and birds.
- [ ] One evidence badge format across CLI, API, UI, and exports.
- [ ] One schema migration note and loader path.

P11.2 Integrated UI and exports
- [ ] One navigation model for Light, Species, Water, Optimize, Birds, Change.
- [ ] One export bundle: CSV, GeoJSON, JSON, and a reproducibility manifest.
- [ ] Add a scenario permalink and a job permalink.

P11.3 Benchmark, reproducibility, and docs
- [ ] One campus benchmark and one city pilot benchmark.
- [ ] One clean-clone reproduction script.
- [ ] Docs for every new method and API.
- [ ] A limitations page and a publication-readiness memo.

P11.4 v0.3.0 release
- [x] Release notes and known gaps.
- [x] Dashboard and CI green.
- [x] Tag and release after maintainer approval.

Acceptance criteria:

- A user can run a scenario and see shade, water, cost, birds, and a Pareto archive.
- A clean clone reproduces the benchmark from a manifest.
- The docs describe every method and limit.
- The v0.3.0 tag and GitHub release exist.

## 7. Cross-cutting workstreams

### Validation

- Solar position against NOAA/SPA and published test cases.
- Shadow geometry against analytic shapes and a small Radiance/SOLWEIG comparison.
- Shade metrics against field/orthophoto observations and sensitivity analysis.
- Species fit against local expert review and observed performance.
- Growth against local allometry and repeat measurements where available.
- Water against soil-moisture sensors and irrigation records where available.
- Optimization against a toy front and a held-out scenario.
- Off-inventory against a permitted field sample.
- Birds against eBird holdout and expert review.

### Uncertainty and evidence

Every output carries:

- method name and code version;
- evidence tier;
- uncertainty interval or ensemble range;
- input data hashes;
- known confounders.

The UI never shows a point estimate without its tier and range.

### Performance

- Representative days and time steps first; full-year mode optional.
- 1 m core grid; 0.5 m for a small scene.
- Precompute shadows for repeated dates; cache by scene hash and sun vector.
- Use spatial indexing and vectorised NumPy.
- Use a process pool, not threads, for CPU work.
- Surrogate only after the full evaluator is validated.

### Security and privacy

- No accounts in the app; the deployment boundary is the existing Cloudflare/CWL gateway.
- Off-inventory data is aggregated for public views.
- No owner names, addresses, or private photos in tracked files.
- Parcel and LiDAR licences are recorded before use.
- The assistant remains opt-in and shell-capable; do not expose the raw port.

### Publication

- P7 methods/integration paper.
- P8 optimization/visualization paper.
- P9 remote-sensing/value-of-information paper.
- P10 ecology paper only with an ecology partner and field data.
- P11 software paper.
- Every paper uses the same evidence-tier and limitation language as the app.

## 8. Risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Compute explosion | A full city-year optimization is infeasible | Representative days, surrogate, spatial decomposition, checkpoints |
| False precision | Users treat a scenario as a measurement | Evidence tiers, ranges, limitations, UI badges |
| Shadow model mismatch | Wrong siting decisions | Validate against NOAA, analytic shapes, Radiance/SOLWEIG, field shadows |
| Species trait gaps | Misleading species ranking | Source every trait; show confidence; expert review; fallback to "unknown" |
| Growth calibration gap | Generic curves mislead | Label as scenario; use local allometry; do not claim calibration |
| Water model oversimplification | Wrong irrigation cost | Soil volume and climate sensitivity; field sensors; ranges |
| Off-inventory privacy | Harm to private owners | Aggregate, no owner data, permissioned field validation |
| Bird overreach | False population claims | Relative abundance vs density vs survival; prior tier; expert review |
| Pareto clutter | Pretty but unusable UI | Linked views, slices, brushing, projection-loss indicator |
| Copyleft contamination | Licence risk | Reimplement; optional permissive adapters; record in software landscape |
| Scope creep | No phase closes | One phase at a time; P11 integration gate |

## 9. "Crazy ideas" backlog

These are recorded, not queued. They become phases only if the core programme succeeds.

- **Shade equity routing**: pedestrian cool corridors and "shade deserts" at 3 pm in August.
- **Shade reciprocity**: buildings shade trees; trees shade buildings; net shade balance.
- **Building energy and solar PV tradeoff**: cooling, heating, and rooftop PV in one objective.
- **Shade credit**: a measurable credit for private trees that provide public shade.
- **Water budget**: cost per shade-hour and cost per stress-day avoided.
- **Climate-analog species fit**: match Vancouver sites to future analogue climates.
- **Pollen, allergen, and BVOC**: species selection that accounts for ozone and health.
- **Stormwater and air quality**: add interception and deposition co-benefits.
- **Pollinators, bats, and arthropods**: extend the habitat layer beyond birds.
- **3D acoustic habitat**: canopy structure and noise mapping for wildlife.
- **Digital twin / AR field view**: hold a phone up and see the future shade and species.
- **Agentic objective elicitation**: the assistant interviews the planner, proposes weights,
  and a human approves them; the optimizer does the math.
- **Real options under climate uncertainty**: when to plant, wait, or replant.
- **Maintenance and wind risk**: include failure risk and crew cost.
- **Life-cycle carbon**: nursery, irrigation, maintenance, and disposal.
- **Urban forest bonds / ecosystem-service credits**: only after the measurement is defensible.

## 10. Recommended sequence and decisions

Recommendation 1: run P7 first. Nothing in P8-P10 is credible without a tested shade and
species layer.

Recommendation 2: run P8 second. It creates the solver and archive that P9 uses for the
value-of-information experiment.

Recommendation 3: run P9 third. The off-inventory layer changes the population that P8
optimizes; do not freeze the optimization benchmark before this test.

Recommendation 4: run P10 fourth. Birds become an additional objective on a stable scenario
contract.

Recommendation 5: run P11 last. Do not tag or release before the benchmark, docs, and
limitations are ready.

Recommendation 6: one active phase at a time, one parent issue, one branch. P9 and P10 may
be developed by separate agents only after P8.1 and P7.2-P7.4 are stable, and only with an
explicit maintainer decision.

Recommendation 7: use "off-inventory urban trees" in technical writing. Keep "shadow urban
forest" as a communication nickname, clearly labelled.

Recommendation 8: frame the contribution as integration and decision semantics, not new
physics. The first paper should be the marginal-shade/species-fit methods paper.

## 11. Definition of done

The programme is done when a planner can:

1. pick a date, time, and target surface;
2. see building shade, canopy shade, and the marginal shade of a candidate tree;
3. see which species fit that light/water regime, how they grow, and what irrigation costs;
4. run a multi-decade, multi-objective planting plan;
5. explore the fuzzy Pareto front in 3D and load any solution as a scenario;
6. include off-inventory trees with confidence and see whether the plan changes;
7. see bird habitat and a prior-driven demographic projection with honest uncertainty;
8. export the result with methods, evidence tiers, and limitations.

That is the v0.3 lab.
