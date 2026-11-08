# P52: Lower Mainland candidate-data honesty

Date: 2026-11-08

## Decision

The off-inventory layers for Surrey, Burnaby, and Coquitlam still contain candidate
points and confidence/height fields. They do **not** have known-good candidate-species
labels. The portal therefore no longer presents candidate conifer/deciduous colors or
mapped species-group counts for those three instances.

- Surrey, Burnaby, Coquitlam: neutral candidate color; confidence/height/context only.
- Vancouver: candidate species scoring remains visible as **screening**, with the
  existing no-known-good-candidate-labels caveat.
- No species claim is added for any Lower Mainland candidate.
- Inventory-only validation remains separate from candidate scoring.

This is a UI and wording change. It does not change the P46 model, candidate data,
sampling, tree/non-tree screening, or inventory metrics.

## Implementation

`src/fresh_urban_forest/web/static/app.js`

- Added `candidateSpeciesScreening()`. It is true only for the Vancouver instance.
- The off-inventory map layer uses the existing conifer/deciduous colors only when that
  screening is available; otherwise it uses the neutral candidate color.
- The off-inventory summary sets `data-candidate-species` to `screening` or
  `unvalidated`.
- The summary shows mapped species-group counts only for the screening instance.
  The three Lower Mainland instances show: “species groups are not validated for this
  dataset; candidate colors show confidence only.”
- Candidate confidence, height, crown area, and tree/non-tree evidence are unchanged.

`tests/test_web_assets.py`

- Added static guards for `candidateSpeciesScreening` and the unvalidated-species
  message.

## Browser smoke

Local portal: `http://127.0.0.1:8107/` (product-honesty branch, `PYTHONPATH=src`).

Playwright checks after enabling the off-inventory layer:

| Instance | `data-candidate-species` | Mapped groups shown | Unvalidated message |
| --- | --- | --- | --- |
| Surrey | `unvalidated` | no | yes |
| Burnaby | `unvalidated` | no | yes |
| Coquitlam | `unvalidated` | no | yes |
| Vancouver | `screening` | yes | no |

No page errors occurred in the four checks.

## What this does not claim

- It does not validate Surrey/Burnaby/Coquitlam candidate species.
- It does not prove the candidate species model is wrong.
- It does not promote candidates to the public inventory.
- It does not add field, ownership, survival, or LiDAR-shape evidence.
- Vancouver candidate species remain a screening product, not candidate ground truth.

## Verification

```text
node --check src/fresh_urban_forest/web/static/app.js
python scripts/dashboard.py
```
