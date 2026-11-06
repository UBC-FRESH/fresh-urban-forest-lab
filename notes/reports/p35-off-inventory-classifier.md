# P35 off-inventory classifier and QA

Date: 2026-11-06

Status: implemented; browser smoke is clean and the dashboard is green.

Parent issue: #156

## What was added

- A conifer/deciduous classifier and QA report built from public tree inventory labels.
- Off-inventory candidate layers for Surrey, Burnaby, and Coquitlam.
- A classifier API and off-inventory QA panel in the portal.

## Labels and data availability

Known-good inventory labels are available for:

- Vancouver public trees: 184,151 records (species-group labels).
- Surrey public trees: 100,940 records (species-group labels).

Burnaby and Coquitlam **do not have public species inventories** in the available open
data. Their tree tables remain LiDAR/land-cover candidates. They can be scored by the
model, but no known-good confusion matrix is reported for them. The UI and report state
this explicitly; the Burnaby/Coquitlam LCC table is a weak-label diagnostic only.

## Model

- Standardized L2 logistic regression with balanced class weights.
- Features: height, log height, crown width, height/crown-width ratio.
- No land-cover class is used as a predictor; LCC is used only for weak-label diagnostics.
- 500 m spatial-block holdout; 25% of blocks held out.
- Training rows: 258,875; train 193,110; test 65,765.
- Known-good classes: 28,929 conifer and 229,946 deciduous.

## Known-good QA

Pooled held-out confusion matrix:

| | predicted conifer | predicted deciduous |
| --- | ---: | ---: |
| true conifer | 5,498 | 1,383 |
| true deciduous | 9,081 | 49,803 |

- Accuracy: 84.09% (95% Wilson 83.81–84.37%).
- Conifer precision: 37.71% (36.93–38.50%); recall 79.90% (78.94–80.83%); F1 51.24%
  (bootstrap 50.42–51.97%).
- Deciduous precision: 97.30% (97.15–97.44%); recall 84.58% (84.28–84.87%); F1 90.49%
  (90.29–90.67%).
- Brier score: 0.1379.

Per-city held-out results:

- Vancouver: 89.71% accuracy (89.42–90.00%), n=41,339.
- Surrey: 74.57% accuracy (74.02–75.11%), n=24,426. Surrey heights are imputed from
  land cover, so this is a weaker test.

The low conifer precision is the main limitation. The classifier is not suitable for
species-level decisions; it is a screening flag with an explicit error profile.

## Off-inventory layers

| Instance | Candidates | High confidence | Inventory status |
| --- | ---: | ---: | --- |
| Surrey | 243,267 | 233,675 | outside public inventory |
| Burnaby | 215,811 | 198,444 | no public inventory |
| Coquitlam | 287,374 | 89,717 | no public inventory |

Surrey candidates are LCC tree cells at 20 m spacing outside a 5 m public-tree match.
Burnaby and Coquitlam have no public inventory, so all compiled candidates are explicitly
marked `no_public_inventory`; they are not presented as unmatched public records.

Every candidate carries `predicted_group`, `conifer_probability`, `group_confidence`, and
`inventory_status`.

## Interface

- `/api/classifier` serves the report when present.
- The off-inventory panel shows the pooled and per-city confusion matrices, accuracy,
  conifer/deciduous precision/recall with intervals, sample sizes, label sources, and the
  weak-label caveat.
- Candidate map styling uses predicted group: dark green conifer, light green deciduous,
  orange unknown.
- The 3D off-inventory overlay uses the same group colours.

## Limits

- Inventory labels are known-good relative to the inventory, not a field audit.
- Surrey height/crown values are imputed from land cover.
- No known-good Burnaby or Coquitlam species labels are available yet.
- Coquitlam LCC weak agreement is not evidence of accuracy.
- Candidates are screening records, not a census, ownership layer, or species inventory.

## Verification

- Browser smoke: `/surrey/`, `/burnaby/`, and `/coquitlam/` load 2D/3D and the QA panel with no console or page errors.
- `python scripts/dashboard.py`: GREEN, every gate passed.
