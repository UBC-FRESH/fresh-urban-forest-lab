# P32 close-out: Vancouver off-inventory candidate layer

Date: 2026-11-08

Status: complete as a screening product; branch archived without merging.

## Decision

The `feature/p32-off-inventory-als` branch is **20 commits ahead and 16 behind `main`**,
with conflicts in the service, app, HTML, tests, and data-lock docs. Its candidate and
validation products were already copied into the main dataset, so merging the old branch
would overwrite later P34–P44 work.

The branch is therefore **archived, not merged**. The validated data snapshot and reports
are retained on `main`.

## Delivered data snapshot

`data/processed/vancouver_2022/` contains:

- 528,812 detected crowns
- 130,497 matched public trees
- 335,471 off-inventory candidates
- 163,158 likely-private land-proxy candidates
- 129,312 high-confidence candidates image/fusion-scored in P36
- crown polygons, point-support records, audit samples, and human labels

The city app shows the candidate layer, confidence filters, counts, 3D candidates, and
explicit caveats.

## Validation

- Held-out public-tree recall: **76.6%** (95% Wilson 73.9–79.1%; n=1,000)
- Blind human audit, strict uncertain excluded: **78.2%** design-weighted candidate
  precision (bootstrap 71.1–84.7%; n=299)
- Conservative audit (uncertain = non-tree): **75.9%** (68.8–82.6%)
- Estimated tree-like candidates: **262,271**; range **238,587–284,177**
- UBC independent test: **52.64%** recall (4,810/9,138); not a precision test

Precision by confidence band: low 59.2%, medium 83.4%, high 98.6%.

## Limits

- Candidates are not a census and include real trees, missed public records, and
  over-segmentation.
- Land class is a proxy, not ownership.
- The UBC inventory is incomplete.
- No field validation; no species claim for Vancouver candidates beyond the P36 image
  screening.
- Counts remain screening ranges, not operational tree totals.

## Retained reports

The P32 reports are copied into `notes/reports/p32-*.md`, including the blind human
verification packet, crown polygons, attributes, city metrics, UBC test, and baseline
validation.
