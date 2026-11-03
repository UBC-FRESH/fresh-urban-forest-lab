# ADR 0005: Model marginal shade and carry an evidence tier

Status: proposed
Date: 2026-11-03
Issues: #40, #41, #42, #43, #44

## Context

The prototype can measure canopy cover, detect crowns, compare acquisitions, and project a
simple planting scenario. It cannot say whether a particular tree adds shade at a
particular time, because it does not model buildings, terrain, or the existing canopy as
competing shade sources. A tree in a closed canopy or a deep building shadow can have a
large crown and almost no marginal effect on pedestrian shade.

The programme also adds models that are not locally calibrated: species traits, water
balance, growth and vigour, irrigation cost, off-inventory detection, and bird demography.
If these are presented as measurements, the result will be false precision.

## Decision

- Treat **marginal, time-integrated, effective shade** as the tree-level shade output, not
  canopy cover. Compute it against a building-only and existing-canopy baseline.
- Separate building shade, existing-canopy shade, and candidate-tree shade in the data
  model, API, UI, and exports.
- Couple the shade regime to species fit, water balance, growth, vigour, drought stress,
  and irrigation cost, with explicit uncertainty.
- Give every output an evidence tier: `measured`, `physics`, `calibrated`, `scenario`, or
  `prior`. A number without a tier is a defect.
- Keep the official inventory and the off-inventory/augmented layer separate and joinable.
  Use "off-inventory urban trees" as the technical term; "shadow urban forest" is a
  communication nickname only.
- Treat bird relative abundance, density, and survival as different quantities. A
  prior-driven demographic projection is labelled as such until local mark-recapture data
  exists.
- Frame the research contribution as integration and decision semantics, not as a new
  radiative-transfer or optimization algorithm.

## Consequences

- The shade model is more expensive than a canopy-cover metric, so it needs representative
  days, caching, and a surrogate for optimization.
- The UI must show ranges and method badges, which adds visual complexity.
- The off-inventory layer cannot be published at owner-address resolution.
- Bird outputs will be less precise than a canopy metric, but honest.
- The programme can produce a defensible methods paper, an optimization paper, an
  off-inventory value-of-information paper, and a software paper without overclaiming.

## Alternatives considered

- **Use canopy cover as the shade proxy.** Rejected: it cannot distinguish a shaded site
  from a sunlit one and would misrank species and planting locations.
- **Use a single clear-sky noon shadow snapshot.** Rejected: it misses morning/afternoon
  and seasonal geometry and overstates the value of a tree that only shades at noon.
- **Adopt an existing microclimate model as the core.** Rejected as a hard dependency:
  licence, runtime, and data-assimilation costs. It remains a validation benchmark.
- **Publish a single "best" planting plan.** Rejected: it hides tradeoffs and uncertainty.
  The programme uses a Pareto archive and a fuzzy front.
- **Call the private-tree layer the "shadow urban forest."** Rejected as a technical term:
  "shadow inventory" already means something else in real estate. Keep it as a nickname.
