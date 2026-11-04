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
- `design/urban-canopy-program-plan.md`: the queued P7-P11 programme for shade, species fit, optimization, off-inventory canopy, and birds.
- `reference/literature-review-shade-optimization-biodiversity.md`: rapid peer-reviewed and grey-literature review, novelty assessment, and citations.
- `reference/shade-review-protocol.md`: P7.1 search protocol, screening log, capability comparison, and frozen claim.
- `reports/detection-and-allometry-2021.md`: first detection validation and local allometry results.
- `reports/field-validation-packet.md`: Main Mall field packet and verification/analysis protocol.
- `reports/observed-change-ubc.md`: same-mask 2015↔2016, 2015↔2021, and 2016↔2021 observed-change products.
- `reports/observed-change-vancouver.md`: City 2018↔2022 product and browser-assisted tile retrieval.
- `reports/p8-optimization-pareto.md`: Fresh Solutions scalarisation benchmark, surrogate error, archive, and Pareto explorer.
- `reports/p8-benchmark-evidence.json`: machine-readable whole-campus and convergence evidence.
- `reports/growth-calibration-readiness.md`: why the current inventory cannot support growth calibration.
- `reports/p12-arbor-method-mining.md`: P12 close-out, licence evidence, gate results, and the P13 recommendation.
- `reports/p13-als-ground-validation.md` and `.json`: P13.2 real LidarBC tile validation, class-2 recall, HAG, and noise caveats.
- `releases/v0.2.0.md`: draft release notes; not tagged.
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
