# P71 street-tree ground-plane sanity gate

Parent issue: #332
Branch: `feature/p71-ground-plane`
Status: complete

## Goal

Test whether a level-camera ground-plane check can separate plausible tree bases from boxes
whose bottom-centre depth lies on buildings, vehicles, sky, or other non-ground surfaces.

## Approach

- Add a documented ground-plane range/ratio helper with unit tests.
- Reconstruct source detections and actual image dimensions.
- Test camera heights 2.0, 2.5, and 3.0 m and a depth/range interval of 0.5-2.0.
- Validate the gate against the P69 200-candidate semantic audit.
- Publish an external sample-only ground-supported subset; do not touch the canonical layer.
- Report limitations, especially unmodeled camera pitch.

## Tasks

- [ ] P71.1 Ground-plane model, reconstruction, and tests
- [ ] P71.2 200-candidate validation and sensitivity
- [ ] P71.3 External diagnostic subset and summary
- [ ] P71.4 Report, docs, PR, and approval gate
