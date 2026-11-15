# P69 street-tree detector and trunk-base audit

Status: implementation complete; PR pending approval.

## 200-candidate mask audit

A deterministic sample of 200 candidates was drawn as 50 per stratum:

- single-view, public-tree match within 8 m;
- single-view, no public-tree match within 8 m;
- multi-view, matched;
- multi-view, unmatched.

The existing OneFormer model was re-run on the 199 unique source images.

### Box composition

| Measure | Result |
| --- | ---: |
| Median tree-mask fraction inside box | **0.703** |
| Tree-mask fraction p25 / p75 | 0.548 / 0.849 |
| Boxes with tree fraction < 0.50 | **42 / 200** |
| Boxes with tree fraction < 0.25 | **11 / 200** |

### Bottom-centre semantic class

The pixel at the box bottom centre is where the current projection places the tree base. Only
**87 / 200 (43.5%)** were labelled `tree`. The remaining labels included:

| Label | Count |
| --- | ---: |
| building | 27 |
| car | 21 |
| sky | 14 |
| sidewalk/pavement | 10 |
| plant | 8 |
| fence | 7 |
| grass | 7 |
| road/route | 6 |
| other | 13 |

By stratum, the bottom-centre label was `tree` for 18/50 single matched, 18/50 single
unmatched, 24/50 multi-view matched, and 27/50 multi-view unmatched. Multi-view candidates
are somewhat better on this cue (51/100 vs 36/100), but the margin is not enough to call the
layer reliable.

Contact sheets (operator artifacts, not committed):

- `/srv/shared-data/gep/ws4/external/street_trees/p69_audit_sheets/p69-audit-sheet-1.png`
- `.../p69-audit-sheet-2.png`
- `.../p69-audit-sheet-3.png`
- `.../p69-audit-sheet-4.png`

Machine-readable sample: `notes/reports/p69-mask-audit.json`.

## Trunk-detection trial

`IDEA-Research/grounding-dino-tiny` (Apache-2.0) was prompted with `tree trunk.` on 20
stratified images. No production integration was made.

- 20/20 images had at least one trunk detection at score ≥0.25;
- 14/20 at ≥0.35;
- 13/20 at ≥0.40;
- only **3/20** best trunk boxes overlapped the current candidate box.

Visually, many detections were trunks at the image margin, poles, or partial trees rather
than the tree associated with the current candidate. The prompt is not a reliable
replacement for the current mask geometry. Trial artifacts:

- `/srv/shared-data/gep/ws4/external/street_trees/p69_trunk_trial.png`
- `notes/reports/p69-trunk-trial.json`

## Confidence subset

A sample-only multi-view subset was written to:

`/srv/shared-data/gep/ws4/external/street_trees/street_tree_candidates_multiview_sample.geojson`

- canonical layer: **19,790** candidates;
- multi-view subset: **8,608** candidates (43.5%);
- public-tree matches within 8 m: **2,610 / 8,608 (30.3%)**;
- canonical match fraction: 6,078 / 19,790 (30.7%).

View count changes the candidate mix but does not improve the inventory-match fraction. The
subset is a screening convenience layer, not a probability or precision tier.

Summary: `notes/reports/p69-confidence-sample.json`.

## Interpretation

The main failure is not FOV. It is box composition and the depth point at the bottom centre:
more than half of the audit boxes put the "tree base" on a building, car, road, sky, or other
non-tree surface. Multi-view fusion helps slightly but does not solve it.

The next detector should explicitly identify a trunk/base or use a ground-plane constraint.
Adding more KartaView images would mostly replicate the same box errors.

## Gate

- Canonical 19,790-feature layer unchanged.
- Multi-view subset is external and sample-only.
- No tag or release.
- No field validation, precision/recall, ownership, survival, or complete-census claim.
