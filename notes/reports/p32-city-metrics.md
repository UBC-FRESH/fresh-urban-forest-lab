# P32 candidate city metrics

Date: 2026-11-06

Status: P32.6 screening metrics. These are candidate-table aggregates, not a total-tree
inventory.

## Likely-private land proxy

| Metric | Value |
| --- | ---: |
| Candidates | 163,158 |
| High-confidence candidates (≥0.6) | 60,698 |
| Summed crown area | 13,705,044 m² (1,370.5 ha) |
| Crown volume, point estimate | 57,469,944 m³ |
| Crown volume range | 28,735,050–86,205,024 m³ |
| Carbon, point estimate | 42,388,900 kg (42,388.9 t) |
| Carbon range | 21,194,147–63,583,915 kg (21,194–63,584 t) |

The crown area is the sum of candidate crown areas. Crowns overlap, so it is not unique
canopy area. The land proxy is not ownership.

## All candidates

| Metric | Value |
| --- | ---: |
| Candidates | 335,471 |
| High-confidence candidates | 129,312 |
| Summed crown area | 28,284,548 m² (2,828.5 ha) |
| Crown volume, point estimate | 132,038,760 m³ |
| Crown volume range | 66,019,549–198,058,343 m³ |
| Carbon, point estimate | 103,295,300 kg (103,295 t) |
| Carbon range | 51,647,185–154,943,843 kg (51,647–154,944 t) |

## App

The Vancouver City tab now receives these aggregates through `/api/city-metrics` and adds
four cards:

- candidate crowns;
- high-confidence candidates;
- likely-private crowns;
- likely-private carbon range.

A 25 m maximum crown-radius quality filter removes 879 watershed flood segments before
aggregation. Without it, a few hundred huge segments dominated summed area and volume.

The City tab keeps the public-tree metrics separate and shows the off-inventory method and
caveat text.

The off-inventory panel also shows a support ≥1,000 QA count and links to the downloadable
candidate GeoJSON. The panel states that no owner names, addresses, or parcel-level
ownership claims are stored or shown. The 3D HUD names the candidate colours and says the
3D overlay is confidence ≥0.6 only.

## Limits

- These are screening aggregates from the candidate table.
- Candidate precision is not 100%; the validation report gives the count and precision
  evidence.
- Crown area is summed, not unique.
- Carbon is a species-unknown allometric estimate with a ±50% screening envelope.
- No ownership, address, species, or private-access claim is made.
