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

## Why earlier 500s happened

The KartaView CDN proxy (`cdn.kartaview.org/pr:sharp/...`) returns HTTP 500 with body
`azure download error` when its origin storage returns 404. Examples pointed at
`storage1.openstreetcam.org`; direct requests returned `BlobNotFound`. The metadata records
remain after those blobs were removed or migrated.

Storage-host counts in the 10,204 record audit:

- storage1: 3,772
- storage3: 2,724
- storage4: 1,357
- storage5: 813
- other storage hosts: ~1,500
- no URL: 7

The earlier 500-image selection was biased toward dead storage1 records. The corrected
run ranks live storage hosts first and preflights downloads.

## Run

The citywide screen selected 1,200 images across 117 populated cells. The public KartaView
CDN returned usable imagery for 1,167 of them.

- 1,167 images decoded.
- 17,016 tree components.
- 3,462 fused candidates.
- 3,047 single-view candidates and 415 with two or more views.
- 1,005 candidates matched a public tree within 8 m; median matched distance **5.20 m**.

## Off-inventory comparison

Off-inventory is a separate LiDAR candidate population, not ground truth. Of the 3,462
street candidates:

- 694 are within 5 m of an off-inventory candidate;
- 1,804 are within 10 m;
- 3,018 are within 20 m;
- median nearest distance is 9.72 m.

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
