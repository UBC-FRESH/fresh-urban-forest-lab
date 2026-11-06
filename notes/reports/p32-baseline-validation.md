# P32 baseline validation

Date: 2026-11-06

Status: partial P32.7. Held-out public-tree recall and a single visual pre-audit of the
fixed candidate sample are complete. The labels are not an independent human audit and the
independent UBC test is not complete.

Protocol: `notes/p32-validation-protocol.md`
Data lock: `notes/p32-data-lock.md`
Machine-readable result: `data/processed/vancouver_2022/off_inventory_validation.json`

## What was measured

The screening layer has 528,812 detected crowns and 130,497 public-tree matches within 5 m.
Of the 184,151 live public records, 53,654 have no detected match. After building/water
centre exclusion, 336,350 crowns are candidates; 163,459 are in the likely-private land
proxy.

The fixed held-out sample uses 500 m blocks, a 100 m interior buffer, and the hash seed
`p32-2026-11-05`. One quarter of blocks are held out. The public-tree sample is stratified
by the 22 local areas, with 45–46 trees per area.

## Held-out public-tree recall

| Field | Value |
| --- | ---: |
| Sample | 1,000 live public trees |
| Nearest crown within 5 m | 766 |
| Recall | 76.6% |
| 95% Wilson interval | 73.9%–79.1% |
| Matched nearest distance, p50 | 2.05 m |
| Matched nearest distance, p95 | 4.50 m |
| Local areas represented | 22 |

Recall varies by local area: Sunset 93.3%, Kensington-Cedar Cottage 87.0%, Killarney
87.0%, Strathcona 57.8%, Marpole 62.2%, Arbutus Ridge 65.2%, and Shaughnessy 66.7%. The
full by-area table is in the JSON result.

This measures detection of **public records**, not private trees. It does not establish
candidate precision or a census count. Trees outside a local-area polygon were excluded
from the sample frame.

## Fixed orthophoto audit packet

The audit sample is deterministic and drawn from the held-out frame:

| Stratum | Count |
| --- | ---: |
| Low confidence (< 0.5) | 100 |
| Medium confidence (0.5–0.7) | 100 |
| High confidence (≥ 0.7) | 100 |
| Likely private parcel | 60 |
| Street/lane | 60 |
| Public park | 60 |
| Other parcel | 60 |
| Unknown | 60 |
| Orthophoto tiles touched | 114 |

Files:

- `data/processed/vancouver_2022/off_inventory_audit_sample.csv`
- `data/processed/vancouver_2022/off_inventory_audit_sample.geojson`
- `data/processed/vancouver_2022/off_inventory_audit_sample.json`

The City orthophoto host returned HTTP 403 to the build environment. Imagery came from
the public Data For Canada PMTiles mirror of the same City 2022 7.5 cm orthophoto:
`https://data.source.coop/dataforcanada/d4c-datapkg-orthoimagery/processed/ca-bc_vancouver-2022A00055915022_d4c-datapkg-orthoimagery_2022_075mm_v0.1.0-beta.pmtiles`.
The mirror metadata names the City open-data source and the 2022 7.5 cm acquisition.

I completed one visual pass over 300 centre-cropped images. This is **one visual pre-audit**,
not an independent human audit; any label can be wrong. Labels are in
`data/processed/vancouver_2022/off_inventory_audit_labels.csv`. The five contact sheets and
300 individual crops are under `data/processed/vancouver_2022/off_inventory_audit_sheet/`.

| Result | Strict (uncertain excluded) | Conservative (uncertain = non-tree) |
| --- | ---: | ---: |
| Tree labels | 212 | 212 |
| Non-tree labels | 69 | 69 |
| Uncertain labels | 19 | 19 |
| Design-weighted candidate precision | 73.6% | 66.9% |
| Bootstrap 95% interval | 68.1%–79.3% | 61.0%–72.7% |
| Estimated tree-like candidates | 247,572 | 224,850 |
| Estimated candidate range | 229,010–266,731 | 205,241–244,459 |

Precision by confidence band (strict, design-weighted): low 46.4%, medium 91.5%, high
83.7%. The high band is lower than the medium band in this sample; do not treat the
confidence score as a probability.

The estimated range applies to tree-like **candidates**, not a total tree census. It does
not include the public inventory, missed public records, or trees outside the candidate
frame.

## Not yet done

- Independent human verification of the 300 visual labels, or a second blind labeler.
- Height, crown, and carbon error against measured public/UBC records.
- Independent UBC test. The repository has only the coarse UBC demo terrain grid
  (38 m cells), not a 1 m/5 m UBC CHM suitable for this detector.
- Point-cloud per-crown support, variable windows, and seam/multi-peak refinement.
- A total-tree count range that combines public recall, candidate precision, and public
  inventory completeness.

## Reproduction

```bash
python scripts/validate_vancouver_off_inventory.py
python scripts/dashboard.py
```

The crop sheet and label scoring were run as one-off local audit utilities; the fixed
sample, labels, contact sheets, and score JSON are retained under
`data/processed/vancouver_2022/`.

## Reading

- `notes/p32-validation-protocol.md`
- `notes/p32-data-lock.md`
- `notes/reports/p30-vancouver-city.md`
