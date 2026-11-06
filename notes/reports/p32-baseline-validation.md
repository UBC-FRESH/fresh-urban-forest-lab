# P32 baseline validation

Date: 2026-11-06

Status: partial P32.7. Held-out public-tree recall and the fixed orthophoto audit packet are
complete. Candidate precision, the candidate count range, and the independent UBC test are
not complete.

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

The audit sample is deterministic and disjoint from the public recall sample:

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

The CSV has blank `audit_label` and `audit_notes` fields. Labels should be `tree`,
`non-tree`, or `uncertain`. The City orthophoto tile URL is included for each row. The
imagery host returned HTTP 403 to the build environment, so imagery inspection is pending
and no precision number is claimed.

## Not yet done

- Manual orthophoto labels and precision with Wilson interval.
- Candidate count range from precision and missed-public rates.
- Height, crown, and carbon error against measured public/UBC records.
- Independent UBC test. The repository has only the coarse UBC demo terrain grid
  (38 m cells), not a 1 m/5 m UBC CHM suitable for this detector.
- Point-cloud per-crown support, variable windows, and seam/multi-peak refinement.

## Reproduction

```bash
python scripts/validate_vancouver_off_inventory.py
python scripts/dashboard.py
```

## Reading

- `notes/p32-validation-protocol.md`
- `notes/p32-data-lock.md`
- `notes/reports/p30-vancouver-city.md`
