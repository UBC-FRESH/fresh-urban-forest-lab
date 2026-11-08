# P47 Surrey 0.30 m candidate sample audit

Date: 2026-11-08

Status: 200-candidate preflighted sample and blind packet ready; human labels not yet entered.

## Sample

- High-confidence Surrey candidates were stratified across ten current image-probability
  bins, 20 per bin.
- 31 candidates were rejected by the crop preflight.
- 200 candidates passed:
  - minimum crop mean 42.4
  - minimum crop standard deviation 15.3
  - minimum crop maximum 223
- Each candidate was scored with the P46 Surrey-specific 0.30 m model.

Outputs:

- `data/processed/surrey_2025/p47_audit/audit_key.csv`
- `data/processed/surrey_2025/p47_audit/preflight.json`
- `data/processed/surrey_2025/p47_verification_packet/`
- `data/processed/surrey_2025/p47_verification_packet.zip`

The review packet uses the existing P32 blind UI pattern: Conifer/Deciduous/Uncertain,
common-comment checkboxes, notes, progress, filters, export/import, local storage, and
optional server persistence.

## Boundary

- This is a sample audit, not a full candidate rescore.
- No candidate labels exist yet; no precision claim is made.
- Do not promote the 0.30 m candidate layer before the sample is reviewed and scored.
- Review server port used for smoke: 8105.
