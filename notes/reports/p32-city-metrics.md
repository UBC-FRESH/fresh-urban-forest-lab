# P32 candidate city metrics

Date: 2026-11-06

Status: P32.6 screening metrics. These are candidate-table aggregates, not a total-tree
inventory.

## Likely-private land proxy

| Metric | Value |
| --- | ---: |
| Candidates | 163,459 |
| High-confidence candidates (≥0.6) | 60,977 |
| Summed crown area | 26,318,272 m² (2,631.8 ha) |
| Crown volume, point estimate | 146,062,931 m³ |
| Crown volume range | 73,031,543–219,094,503 m³ |
| Carbon, point estimate | 42,444,801 kg (42,444.8 t) |
| Carbon range | 21,222,097–63,667,768 kg (21,222–63,668 t) |

The crown area is the sum of candidate crown areas. Crowns overlap, so it is not unique
canopy area. The land proxy is not ownership.

## All candidates

| Metric | Value |
| --- | ---: |
| Candidates | 336,350 |
| High-confidence candidates | 130,103 |
| Summed crown area | 105,047,556 m² |
| Crown volume, point estimate | 606,472,615 m³ |
| Crown volume range | 303,236,475–909,709,127 m³ |
| Carbon, point estimate | 103,421,246 kg (103,421 t) |
| Carbon range | 51,710,156–155,132,762 kg (51,710–155,133 t) |

## App

The Vancouver City tab now receives these aggregates through `/api/city-metrics` and adds
four cards:

- candidate crowns;
- high-confidence candidates;
- likely-private crowns;
- likely-private carbon range.

The City tab keeps the public-tree metrics separate and shows the off-inventory method and
caveat text.

## Limits

- These are screening aggregates from the candidate table.
- Candidate precision is not 100%; the validation report gives the count and precision
  evidence.
- Crown area is summed, not unique.
- Carbon is a species-unknown allometric estimate with a ±50% screening envelope.
- No ownership, address, species, or private-access claim is made.
