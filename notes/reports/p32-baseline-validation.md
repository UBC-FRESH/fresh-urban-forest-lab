# P32 baseline validation

Date: 2026-11-06

Status: P32.7 validation largely complete. Held-out public-tree recall, a blind human
review of the fixed candidate sample, and the independent UBC test are complete. The
remaining work is close-out/second-reviewer documentation.

Protocol: `notes/p32-validation-protocol.md`
Data lock: `notes/p32-data-lock.md`
Machine-readable result: `data/processed/vancouver_2022/off_inventory_validation.json`

## What was measured

The screening layer has 528,812 detected crowns and 130,497 public-tree matches within 5 m.
Of the 184,151 live public records, 53,654 have no detected match. After building/water
centre exclusion and a 25 m maximum crown-radius quality filter, 335,471 crowns are
candidates; 163,158 are in the likely-private land proxy. The filter removed 879
implausible watershed flood segments.

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

A blind human reviewer completed the packet. The review UI hid the prior AI labels and
saved the labels, common comments, and notes to the review server. The fixed 300-candidate
sample contained one candidate removed by the 25 m crown filter (`off-180636`), leaving 299
scored rows.

| Result | Strict (uncertain excluded) | Conservative (uncertain = non-tree) |
| --- | ---: | ---: |
| Tree labels | 248 | 248 |
| Non-tree labels | 44 | 44 |
| Uncertain labels | 7 | 7 |
| Design-weighted candidate precision | 78.2% | 75.9% |
| Bootstrap 95% interval | 71.1%–84.7% | 68.8%–82.6% |
| Estimated tree-like candidates | 262,271 | 254,589 |
| Estimated candidate range | 238,587–284,177 | 230,905–277,032 |

Precision by confidence band (strict, design-weighted): low 59.2%, medium 83.4%, high
98.6%. The likely-private subset remains a land proxy, not ownership.

The human labels disagree with the prior AI pre-audit on 28.8% of the scored sample
(213/299 agree; 43 prior N became human T; 17 prior T became human N; 4 prior U became
human N; 14 prior U became human T). The human labels supersede the AI labels for
precision.

Common-comment counts: mask underreach/partial crown 88, mask overreach 79, merged crowns
78, hedge/shrub 30, road/sidewalk/lawn 28, roof/building 17, shadow 12, tiny/ornamental
tree 10, car/parking 8, mixed hedge/tree 4, construction/track 2, blurred image 2.

The estimated range applies to tree-like **candidates**, not a total tree census. It does
not include the public inventory, missed public records, or trees outside the candidate
frame.

The independently reviewed labels are in
`data/processed/vancouver_2022/human_verification_packet/p32_human_labels.csv`; the score
JSON is `data/processed/vancouver_2022/off_inventory_human_scores.json`.

## Not yet done

- A second blind reviewer is optional; one human reviewer has completed the packet.
- Height, crown, and carbon error against measured public/UBC records.
- UBC independent test is complete and reported separately; it showed 52.64% recall.
- Point-cloud per-crown support and polygons are built; variable windows and seam/multi-peak
  refinement remain open.
- A total-tree count range that combines public recall, candidate precision, and public
  inventory completeness.

## Reproduction

```bash
python scripts/validate_vancouver_off_inventory.py
python scripts/dashboard.py
```

The crop sheet, review server, and label scoring are local audit utilities. The final
human score is retained as `data/processed/vancouver_2022/off_inventory_human_scores.json`.

## Reading

- `notes/p32-validation-protocol.md`
- `notes/p32-data-lock.md`
- `notes/reports/p30-vancouver-city.md`
