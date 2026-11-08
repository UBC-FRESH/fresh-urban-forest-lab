# P47 Surrey 0.30 m candidate sample audit

Date: 2026-11-08

Status: AI-assisted tree/non-tree pre-audit complete; human species review not performed.

## Sample

- 200 candidates selected from ten current image-probability bins, 20 per bin.
- 26 candidates rejected by crop preflight; replacements taken within each bin.
- 200 accepted crops passed coverage/contrast checks.
- The first attempted sample was not stratified; it was rejected and rebuilt. The result
  below uses the corrected 20-per-bin sample.

## AI-assisted pre-audit

A contact-sheet review was performed as an **AI-assisted visual pre-audit**, not a human
or field audit.

- Tree-like candidates: **97 / 200**
- Non-tree / ambiguous candidates: **103 / 200**
- Population-weighted tree-like share: **29.1%**

Tree-like counts rise sharply with the model probability bin:

| Bin | Tree-like / 20 |
|---|---:|
| 0.0–0.1 | 0 |
| 0.1–0.2 | 3 |
| 0.2–0.3 | 3 |
| 0.3–0.4 | 7 |
| 0.4–0.5 | 8 |
| 0.5–0.6 | 11 |
| 0.6–0.7 | 12 |
| 0.7–0.8 | 15 |
| 0.8–0.9 | 19 |
| 0.9–1.0 | 19 |

The low and middle probability strata are dominated by roofs, roads, driveways, lawns,
and other non-tree features. The species model cannot be fairly audited across the full
candidate layer without first filtering those candidates.

## Artifacts

- `data/processed/surrey_2025/p47_audit/p47_ai_preaudit.csv`
- `data/processed/surrey_2025/p47_audit/preaudit_contact_pages/`
- `data/processed/surrey_2025/p47_preaudit_packet/`

No human labels have been entered and no candidate promotion is made. The 97 tree-like
cases are screening candidates for a future species review, not validated trees.

## Human species review of the tree-like subset

The live review server returned labels for all **97** tree-like candidates:

- conifer: **33**
- deciduous: **53**
- uncertain: **11**

The P46 Surrey 0.30 m model predicts conifer for 91 of 97 candidates. The human labels are
low-information visual labels (384 px crops, no stereo or CHM overlay), so the comparison is
an **agreement check**, not accuracy against truth. Excluding uncertain:

| Prediction | Valid n | Correct | Precision | Recall |
| --- | ---: | ---: | ---: | ---: |
| Conifer | 82 | 32 | **39.0%** | **97.0%** |
| Deciduous | 4 | 3 | 75.0% | 5.7% |

Agreement is **35/86 = 40.7%**. This does not establish that the model is wrong on the
candidate population; it establishes that the visual labels and the model disagree strongly,
and that the labels are not a reliable species ground truth. The inventory-only P46 result
(78.70%) remains the only defensible model validation.

## Decision

- Candidate species performance is **unmeasured**, not proven bad.
- Do not promote or display candidate species labels as validated.
- Keep the inventory-only 78.70% result as inventory QA, not candidate QA.
- Do not use the weak visual labels as a confusion matrix against the model.
- P47 closes **inconclusive** for candidate species; the AI tree-like prefilter is retained
  only as a screening aid.

Labels saved at `data/processed/surrey_2025/p47_audit/p47_tree_human_labels.csv`.
