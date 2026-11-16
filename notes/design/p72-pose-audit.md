# P72 KartaView camera-pose metadata audit

Parent issue: #334
Branch: `feature/p72-pose-audit`
Status: pr-open

## Goal

Determine whether KartaView provides usable camera pitch/roll/FOV metadata for the selected
street-tree images, as a prerequisite to any credible ground-plane retry.

## Scope

- Sample 50 selected images and their 50 sequences.
- Audit photo/sequence fields and metadata-file headers.
- Count nonzero sequence camera FOV values and inspect the metadata 2.0 text format.
- Report feasibility; do not integrate or change data.
- No tag or release without approval.

## Tasks

- [ ] P72.1 Selected-image and sequence metadata audit
- [ ] P72.2 Orientation text inspection and feasibility conclusion
- [ ] P72.3 Report, docs, PR, and approval gate
