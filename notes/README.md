# Notes

Notes are the persistent, agent-friendly context for this project. They hold what a future reader, human or agent, needs and cannot get from the code, the issues, or the changelog alone.

- `notes/adr/NNNN-slug.md`: decisions. One decision per file. Never rewrite an accepted ADR; supersede it with a new one. Start from `adr/0000-template.md`.
- `notes/reference/`: facts with provenance. Record where each fact came from, how it was read, and what is uncertain.
- `notes/`: focused plans that are too long for `ROADMAP.md`. Link each one from its roadmap task, and keep it current while the task is active.
- `notes/reports/`: the close-out report for each phase. Start from `reports/phase-closeout-template.md`. The report is the evidence for the maintainer's approval.

Keep private material out of this directory.

## Current notes

- `design/architecture.md`: the layer diagram, contracts, and deliberate simplifications.
- `design/change-uncertainty-plan.md`: observed change, completeness, validation, and calibration plan.
- `design/urban-canopy-program-plan.md`: the completed P7-P11 programme for shade, species fit, optimization, off-inventory canopy, and birds.
- `design/vancouver-city-pilot.md`: P21 full-city Vancouver data lock, storage budget, processing design, metrics, and acceptance criteria.
- `reference/literature-review-shade-optimization-biodiversity.md`: rapid peer-reviewed and grey-literature review, novelty assessment, and citations.
- `reference/shade-review-protocol.md`: P7.1 search protocol, screening log, capability comparison, and frozen claim.
- `reports/detection-and-allometry-2021.md`: first detection validation and local allometry results.
- `reports/field-validation-packet.md`: Main Mall field packet and verification/analysis protocol.
- `reports/observed-change-ubc.md`: same-mask 2015↔2016, 2015↔2021, and 2016↔2021 observed-change products.
- `reports/observed-change-vancouver.md`: City 2018↔2022 product and browser-assisted tile retrieval.
- `reports/p8-optimization-pareto.md`: Fresh Solutions scalarisation benchmark, surrogate error, archive, and Pareto explorer.
- `reports/p8-benchmark-evidence.json`: machine-readable whole-campus and convergence evidence.
- `reports/p9-off-inventory.md`: Main Mall off-inventory pilot, privacy, and value-of-information results.
- `reference/off-inventory-terminology.md`: terminology, land-class proxy, privacy, and refresh workflow.
- `reference/bird-habitat-methods.md`: guild scope, structural metrics, demographic priors, and evidence tiers.
- `reports/p10-birds.md`: bird habitat, guild relative abundance, prior lambda, and limits.
- `reports/p11-integration.md`: unified report, integration limits, and v0.3.0 release.
- `releases/v0.3.0.md`: v0.3.0 release notes; tagged and released.
- `reports/growth-calibration-readiness.md`: why the current inventory cannot support growth calibration.
- `reports/p12-arbor-method-mining.md`: P12 close-out, licence evidence, gate results, and the P13 recommendation.
- `reports/p13-als-ground-validation.md` and `.json`: P13.2 real LidarBC tile validation, class-2 recall, HAG, and noise caveats.
- `reports/p13-als-ground-sor.json`: P13.3 SOR before/after metrics and low-point policy evidence.
- `reports/p13-closeout.md`: P13 close-out, acceptance evidence, CI, and the P14 recommendation.
- `reports/p14-ground-reference.md` and `.json`: P14 class-2 reference, steep-tile validation, and the optional FEMIC decision.
- `reports/p14-closeout.md`: P14 close-out, acceptance evidence, and the P15 recommendation.
- `reports/p15-ground-reference.md` and `.json`: P15 manual 20 m patch check and the optional-adapter decision.
- `design/femic-ground-adapter.md`: optional sidecar adapter contract, bundle schema, failure modes, and test strategy.
- `adr/0007-optional-femic-ground-adapter.md`: accept the sidecar contract; no default FEMIC change.
- `reports/p15-closeout.md`: P15 close-out, acceptance evidence, and the P16 recommendation.
- `reports/p16-ground-adapter.md`: P16 implementation, contract tests, and the real-tile smoke result.
- `reports/p16-closeout.md`: P16 close-out and the P17 recommendation.
- `reports/p17-closeout.md`: P17 close-out and the P18 recommendation.
- `reports/p18-itd-postprocess-smoke.md`: P18 demo smoke counts and CLI export details.
- `reports/p18-closeout.md`: P18 close-out and the P19 recommendation.
- `reports/p19-merge-audit.md`: P19 chain-collapse audit, guard evidence, and new demo counts.
- `reports/p19-closeout.md`: P19 close-out and the P20 recommendation.
- `reports/p20-anchor-merge.md`: P20 anchor rule, synthetic audit patch, and demo comparison.
- `reports/p20-closeout.md`: P20 close-out and the P21 recommendation.
- `reports/p21-vancouver-city.md`: full Vancouver city pilot close-out, metrics, validation, performance, storage, and limits.
- `releases/v0.2.0.md`: superseded draft; never tagged.
- `reference/data-sources.md`: public UBC, Vancouver, and Metro Vancouver sources, with
  coverage, licences, and traps.
- `reference/software-landscape.md`: comparable inventory, LiDAR, growth, and DSS systems;
  what we borrowed, what we refused to copy, and why.
- `reference/arbor-method-mining.md`: Arbor 1.1.5 source snapshot, clean-room policy,
  candidate matrix, attribution templates, and the first four implemented primitives.
- `adr/0001-seed-and-workflow.md`: use the UBC-FRESH seed.
- `adr/0002-standalone-core.md`: keep the core independent of other lab systems.
- `adr/0003-lidar-and-change-methods.md`: CHM detection and repeat-measures change.
- `adr/0004-scenario-model.md`: immutable dataset plus append-only scenario edits.
- `adr/0005-marginal-shade-and-evidence-tiers.md`: proposed decision to model marginal shade and label every output with an evidence tier.
- `adr/0006-clean-room-method-reuse.md`: reimplement copyleft methods and cite them; never copy copyleft code.
