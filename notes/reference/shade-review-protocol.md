# Shade, species, optimization, and habitat review protocol

Status: protocol and rapid-review log, 2026-11-03. This is the P7.1 method lock.
It does not claim a completed systematic review. It records how to finish one and what
the prototype will and will not claim in the meantime.

## Question

Does a tree-level, building-aware, time-integrated shade and species-fit decision layer
already exist in the peer-reviewed or grey literature, and if not, what is the defensible
contribution?

## PICO

- **Population**: urban trees and canopy in temperate cities, especially Vancouver and the
  Pacific Northwest.
- **Intervention**: tree planting, removal, species selection, irrigation policy, or
  management scenario.
- **Comparison**: building shade, existing canopy, no-tree baseline, or current practice.
- **Outcome**: effective shade, light regime, growth, vigour, drought stress, irrigation
  cost, ecosystem services, biodiversity, or decision quality.

## Search strategy

Databases and indexes:

- Web search for discovery and grey literature;
- Crossref for bibliographic verification and DOI resolution;
- Google Scholar and publisher pages for citation chaining;
- municipal, provincial, federal, and university sources for local policy and data.

Query families:

1. `urban tree shade building shadow microclimate thermal comfort`
2. `street tree shade provision canopy cover building shade`
3. `tree species selection urban drought stress growth vigour irrigation`
4. `urban tree water use irrigation requirement cost`
5. `multi-objective optimization urban forest planting Pareto front`
6. `many-objective optimization high-dimensional Pareto visualization`
7. `LiDAR urban tree inventory individual tree detection private property`
8. `trees outside forests private residential canopy remote sensing`
9. `LiDAR vegetation structure urban bird richness density survival`
10. `urban forest decision support system i-Tree SOLWEIG UMEP Radiance CitySim Ladybug`

Inclusion:

- peer-reviewed empirical, review, or methods paper;
- grey literature only for local policy, tool capability, or data context;
- explicit building/tree shade, species/water/growth, optimization, off-inventory canopy,
  or bird habitat relevance;
- English language;
- 1990-2026, with emphasis on 2015-2026.

Exclusion:

- ornamental planting advice without a method;
- vendor marketing without documentation;
- studies that only report a canopy-cover map and no management decision;
- papers that cannot be verified through a DOI, publisher page, or stable repository.

## Screening log

| Step | Result | Notes |
| --- | --- | --- |
| Discovery searches | 10 query families | Rapid search, 2026-11-03 |
| Records screened | about 80 titles and snippets | Not a full PRISMA count |
| Full-text or abstract check | about 30 | Core papers and local grey literature |
| Included for the rapid review | 35+ | See `literature-review-shade-optimization-biodiversity.md` |
| Systematic full-text screen | pending | P7.1 completion criterion |
| Librarian search review | pending | Recommended before a novelty claim is frozen |

## Extraction fields

- citation and DOI/URL;
- study type and location;
- shade source: building, tree, terrain, or mixed;
- time resolution: snapshot, hourly, daily, seasonal, annual;
- spatial resolution and scale;
- tree representation: 2D cover, 3D crown, point cloud, or species trait;
- decision output: map, ranking, scenario, optimization, or none;
- growth/water/species linkage;
- uncertainty treatment;
- licence and code availability.

## Capability comparison (method lock)

| Tool or family | Building shade | Tree shade | Time resolution | Tree-level decision support | Main gap for this project |
| --- | --- | --- | --- | --- | --- |
| SOLWEIG / UMEP | Yes | Yes | Sub-hourly to annual | No | Microclimate model, not a tree inventory/planting optimizer |
| Radiance | Yes | Yes | Configurable | No | Geometry and daylight engine, not a management DSS |
| CitySim | Yes | Partial | Hourly/annual | No | Urban energy model, not tree-level species/water |
| Ladybug / Grasshopper | Yes | Yes | Configurable | No | Parametric design tool, not an open inventory DSS |
| i-Tree | Simplified | Simplified | Annual/benefit transfer | Partial | Not a daily 3D shadow model; limited species/water coupling |
| CanopyFit / UBC SEEDS | Yes | Yes | Scenario/snapshot | Partial | Local planting priority, not tree-level marginal shade + optimization |
| This prototype (P7) | Yes | Yes | Daily/seasonal/annual | Yes | 2.5-D crown shadows, no penumbra or CFD; not yet field-validated |

## Benchmark target

P7 validates the solar and shadow kernel against:

1. NOAA solar-position equations and published test cases;
2. analytic shadow length and direction for a box and an ellipse;
3. a small synthetic scene with known building and tree masks;
4. a future Radiance or SOLWEIG comparison on the same scene, recorded as a benchmark,
   not as a runtime dependency.

P7 does **not** validate against a field shade survey. That is a later field campaign.

## Frozen claim

The defensible claim is:

> A tree-level, time-integrated, building-aware marginal-shade layer, coupled to species
> water/growth/vigour and used inside a spatio-temporal multi-objective planting
> optimization, is an uncommon integration in an open urban-forest decision-support tool.

The claim is not:

- a new radiative-transfer model;
- a new optimization algorithm;
- a field-validated shade or growth model;
- a replacement for SOLWEIG, Radiance, i-Tree, or a municipal inventory.

The contribution is the integration and decision semantics. The literature review must be
upgraded to a systematic search before a journal submission makes a stronger claim.
