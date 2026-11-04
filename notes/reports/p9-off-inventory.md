# P9 close-out: off-inventory canopy and value of information

Date: 2026-11-04
Phase: P9
Parent issue: #42
Branch: `feature/p9-off-inventory`
Implementation head: pending at report write; refreshed at PR queue
Status: ready for review

## Summary

P9 adds a separate **off-inventory urban-tree** candidate layer. It detects crowns from a
high-resolution CHM patch, matches them to the official inventory, keeps unmatched crowns
as confidence-scored candidates, and tests whether adding them changes baseline canopy
accounting and the P8 planting decision.

The pilot is Main Mall, UBC 2021 LiDAR. It is a screening layer, not a confirmed private-tree
census.

## Acceptance evidence

| Criterion | Status | Evidence |
| --- | --- | --- |
| Off-inventory layer exists with confidence and land class | met | `off_inventory.json` / `.geojson`; 500 candidates |
| Reconciliation separates unmatched, missed, and false-positive risk | met with limit | matched/unmatched counts and caveats; no field verification |
| Value-of-information experiment reports whether the plan changes | met | official vs augmented P8 comparison |
| No private owner data tracked or exposed | met | aggregate/candidate-level fields only |
| Dashboard green | met | dashboard GREEN; 291 tests |

## Pilot method

- Patch: `-123.255,49.258,-123.245,49.265` (Main Mall)
- CHM: UBC 2021 `CHM_1m.tif`
- Detection grid: 700 cells maximum per axis
- Detector: local maxima + marker-controlled watershed
- Match tolerance: 4 m greedy nearest
- Candidate confidence threshold: 0.3
- Candidate cap: 500
- Land class: inside/outside analysis boundary, ownership unknown

## Pilot result

- Detected crowns: **5,536**
- One-to-one inventory matches: **1,409**
- Candidates: **500** (cap)
- High confidence (>= 0.6): **435**
- Candidate crown area: **8.3 ha**
- Ownership: **unknown for every candidate**; no parcel layer was available

The 500 cap is a screening choice. Many unmatched crowns are over-segmentation, missed
inventory records, or real off-inventory trees; the layer does not distinguish them without
field work.

## Value of information

Same P8 sites, budget, horizon, seed, and scalarization budget:

| Metric | Official | Augmented |
| --- | ---: | ---: |
| Live-tree count | 9,259 | 9,759 |
| Crown volume | 2.855M m³ | 3.669M m³ |
| Above-ground carbon | 3,827 t | 5,024 t |
| Best-shade archive solution | 101,149 m²h | 101,149 m²h |
| Archive size | 7 | 7 |
| Best-shade plan Jaccard | — | 1.00 |
| Changed sites | — | 0 |

The layer changes **baseline canopy and carbon accounting** substantially (+814.6k m³
crown volume, +1.2k t carbon), but it does not change the best-shade planting plan in this
pilot. The candidates sit in already-shaded Main Mall canopy, so they do not change the
sampled sun fraction at the candidate planting sites.

This is a useful decision result: an imperfect layer can improve measurement and habitat
accounting without changing the planting recommendation. It is not a claim that off-inventory
trees are irrelevant.

## UI and API

- Sidebar **Off-inventory canopy** summary: candidates, high-confidence count, candidate
  area, detected/matched counts, and VOI plan change/canopy/carbon deltas.
- Map layer toggle **off-inventory**, off by default, orange confidence/height-scaled points.
- `GET /api/off-inventory`
- `GET /api/off-inventory.geojson`
- `GET /api/off-inventory/value`
- `fresh-urban-forest off-inventory ... --voi`

The demo files are tracked in `data/demo/ubc_core/`.

## What was not validated

- No permitted private-property field sample.
- No parcel or ownership layer.
- No completed field reference patch.
- No species identification for candidates.
- No correction for over-segmentation or missed inventory.
- No claim that the candidate cap is a census.

## Privacy and terminology

- Technical term: **off-inventory urban trees**.
- “Shadow urban forest” is a nickname, not a scientific term.
- No owner names, addresses, private photos, or parcel-level ownership claims are tracked
  or exposed.
- The public layer is aggregate/candidate-level only.

## Risks carried forward

- A candidate can be a false positive.
- Carbon/canopy totals depend on unknown species and generic allometry.
- The 500 cap and confidence threshold can change the reported value.
- A parcel layer would improve land class but adds licence and privacy obligations.
- The plan-change result is specific to the Main Mall pilot and P8 settings.

## Next phase

P10 adds bird habitat and demography. It should use the official and augmented canopy
layers only after the P9 candidate layer is clearly labelled as screening data.

No tag or release is created by this phase.
