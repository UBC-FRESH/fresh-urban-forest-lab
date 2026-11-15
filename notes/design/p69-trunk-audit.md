# P69 street-tree detector and trunk-base audit

Parent issue: #328
Branch: `feature/p69-trunk-audit`
Status: active

## Goal

Determine whether the current semantic-mask boxes can be improved by an open promptable
segmentation/trunk trial and a transparent confidence filter. The canonical 19,790-feature
layer remains unchanged.

## Approach

1. Draw a deterministic 200-candidate audit sample across view-count, uncertainty, and
   inventory-match strata.
2. Re-run the existing OneFormer model on the 200 source images and measure, inside each
   box, tree-mask fraction, non-tree fractions, bottom-centre class, and box area.
3. Render contact sheets for visual review and preserve a machine-readable sample manifest.
4. Trial an open-licensed promptable segmentation model on a smaller image sample using the
   existing boxes as prompts; report whether it isolates a plausible tree instance/trunk.
5. Define confidence tiers from view count, uncertainty, and score; publish a sample-only
   filtered layer and compare counts/matches with the canonical layer.
6. No canonical overwrite, tag, or release without approval.

## Limits

- Screening audit only; no field validation, precision/recall, ownership, survival, or
  complete-census claim.
- The audit describes the current model; it does not prove detector accuracy.
- Promptable segmentation is an experiment, not a production dependency.
