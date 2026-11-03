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
- `reports/detection-and-allometry-2021.md`: first detection validation and local allometry results.
- `reports/field-validation-packet.md`: Main Mall field packet and verification/analysis protocol.
- `reports/observed-change-ubc.md`: same-mask 2015↔2016, 2015↔2021, and 2016↔2021 observed-change products.
- `reports/observed-change-vancouver.md`: City 2018↔2022 product and browser-assisted tile retrieval.
- `reports/growth-calibration-readiness.md`: why the current inventory cannot support growth calibration.
- `releases/v0.2.0.md`: draft release notes; not tagged.
- `reference/data-sources.md`: public UBC, Vancouver, and Metro Vancouver sources, with
  coverage, licences, and traps.
- `reference/software-landscape.md`: comparable inventory, LiDAR, growth, and DSS systems;
  what we borrowed, what we refused to copy, and why.
- `adr/0001-seed-and-workflow.md`: use the UBC-FRESH seed.
- `adr/0002-standalone-core.md`: keep the core independent of other lab systems.
- `adr/0003-lidar-and-change-methods.md`: CHM detection and repeat-measures change.
- `adr/0004-scenario-model.md`: immutable dataset plus append-only scenario edits.
