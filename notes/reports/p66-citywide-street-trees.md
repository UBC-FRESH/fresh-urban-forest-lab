# P66 citywide street-level tree candidate sample

Status: implementation complete; PR review pending.

## Coverage audit

- 118 boundary-constrained 1 km grid cells.
- Each cell queried within 500 m of its centre.
- 10,204 unique KartaView image records in the metadata audit.
- Median 100 metadata records per cell; some cells returned none.
- Capture years are predominantly 2016 and 2017, with smaller 2018/2019 coverage.
- Image CDN availability is lower than metadata availability; some older URLs return 500.
- The API rate-limited the first uninterrupted sweep; the production run retries 429s and
  throttles requests.

Coverage summary: `notes/reports/p66-coverage-summary.json`.

## Run

The citywide screen selected 500 images across 117 populated cells. The public KartaView
CDN returned usable imagery for 85 of them.

- 85 images decoded.
- 1,023 tree components.
- 258 fused candidates.
- 225 single-view, 16 two-view, 10 three-view, and 7 four-view candidates.
- 70 candidates matched a public tree within 8 m; median matched distance **5.32 m**.

## Off-inventory comparison

Off-inventory is a separate LiDAR candidate population, not ground truth. Of the 258 street
candidates:

- 41 are within 5 m of an off-inventory candidate;
- 106 are within 10 m;
- 184 are within 20 m;
- median nearest distance is 11.73 m.

This is descriptive overlap only. It does not merge the layers or establish that a street
candidate and a LiDAR candidate are the same tree.

## Complementarity

Street candidates are published as a separate `street_level_cv` layer. They are not merged
with the LiDAR off-inventory layer or official inventory.

## Limits

- Grid sample, not a complete image census.
- KartaView FOV remains assumed at 60°.
- Imagery is predominantly 2016-2018; inventory is current.
- Single-view candidates dominate when image coverage is sparse.
- No precision, recall, field-validation, survival, ownership, or citywide census claim.
