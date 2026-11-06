# Off-inventory conifer/deciduous classification and QA

Status: active P35 implementation, 2026-11-06. See
`notes/reports/p35-off-inventory-classifier.md` for the completed QA results.

Parent issue: #156

## Goal

Compile off-inventory candidate layers for the Surrey, Burnaby, and Coquitlam portal
instances, and add a documented conifer/deciduous classifier with confusion-matrix and
confidence-interval QA to the interface.

This is a screening classifier, not a species inventory. It must not claim field
identification, ownership, or a census.

## Data and labels

Training uses `data/processed/vancouver_2022/map_trees.json.gz` and
`data/processed/surrey_2025/map_trees.json.gz`; the model/report artifacts are in
`data/processed/lower_mainland_classifier/`. Off-inventory outputs are in each city root.

The available known-good labels are the public tree inventories:

- Vancouver public trees: 184,151 records with species/group labels.
- Surrey public trees: 100,940 records with species/group labels.
- UBC campus inventory: independent campus test bed.

Burnaby and Coquitlam currently have **no public tree inventory with species labels**.
Their current tree tables are LiDAR or land-cover candidates. They can be scored by the
model, but they cannot provide a known-good confusion matrix until the delivered municipal
inventories arrive. The report and UI must say this explicitly.

## Features

Every training and candidate record uses features available consistently across cities:

- height (m), log height, crown width (m), DBH (cm), crown ratio;
- height/crown ratio and crown volume proxy;
- Metro LCC 2020 class indicators: conifer, deciduous, shrub, other;
- local LCC tree fraction and open/built context at a fixed radius;
- optional terrain/elevation and local canopy statistics.

The land-cover class is a context feature, not a species label. Surrey heights are
imputed from land cover, so Surrey is reported as a weaker external test and not used to
claim independent LiDAR accuracy.

## Model

A transparent logistic-regression baseline with standardized features, L2
regularization, and balanced class weights. It is deliberately small and inspectable; no
deep model is justified by the available tabular labels. The model artifact stores
coefficients, feature means/scales, training counts, threshold, and limitations.

## Spatial validation

Use deterministic 500 m blocks. Hold out 25% of blocks for Vancouver and Surrey. Report:

- 2×2 confusion matrix by city and pooled;
- accuracy, conifer/deciduous precision and recall, and F1;
- 95% Wilson intervals for accuracy and per-class precision/recall;
- stratified bootstrap intervals for F1;
- Brier score and a calibration table;
- label counts by source city;
- external agreement on Burnaby/Coquitlam LCC weak labels, clearly separated from
  known-good accuracy.

No Burnaby/Coquitlam known-good confusion matrix is reported until labels exist.

## Off-inventory outputs

Each new instance gets:

- `off_inventory.json` summary;
- `off_inventory.geojson.gz` candidates with predicted group, conifer probability, model
  confidence, and land-context label;
- `off_inventory_3d.json.gz` high-confidence candidates for the 3D overlay;
- `classifier_report.json` for the QA interface.

Surrey off-inventory candidates are LCC tree cells outside a 5 m public-tree match.
Burnaby and Coquitlam have no public inventory, so all compiled candidates are explicitly
labelled `no_public_inventory` rather than pretending they are unmatched public records.

## Interface

Add a classifier QA panel to the off-inventory section:

- confusion matrix, per-class precision/recall/F1 with 95% intervals;
- sample sizes and label sources;
- model method and feature list;
- explicit "no known-good labels yet" state for Burnaby/Coquitlam;
- candidate predicted-group legend and confidence floor.

## Tasks

- P35.1 Lock labels/features and implement the classifier and metrics.
- P35.2 Build the off-inventory layers for Surrey, Burnaby, and Coquitlam.
- P35.3 Add classifier API/UI QA and candidate styling.
- P35.4 Validate, document, test, and prepare close-out.

## Acceptance

- All three new instances expose an off-inventory candidate layer.
- Every candidate has a predicted group, probability, and confidence.
- The QA panel shows a confusion matrix and confidence intervals for known-good labels.
- Burnaby/Coquitlam are marked unlabelled, with weak-label agreement reported separately.
- Dashboard is green and browser smoke is clean.
