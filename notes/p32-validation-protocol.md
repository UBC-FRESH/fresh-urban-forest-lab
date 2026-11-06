# P32 validation protocol

Date fixed: 2026-11-05

Status: P32.1 protocol. The first screening build is a baseline; this protocol is fixed
before parameter tuning and before any validation sample is inspected.

## Operational targets

- **Detected crown**: a CHM local-maximum segment with height ≥ 3 m.
- **Off-inventory candidate**: a detected crown with no one-to-one public-tree match
  within 5 m, whose centre is outside the P30 building and water masks.
- **Likely private parcel proxy**: a candidate centre inside a property parcel and inside
  residential zoning, and not inside a park or within 7.5 m of an OSM road centreline.
  This is a land-context proxy, not ownership.
- **Public canopy**: an area matched to a public inventory tree; public parks and streets
  are reported separately from the likely-private proxy.
- **Target population**: candidate crowns, not a census of stems. Multi-stem trees and
  over-segmentation are allowed and must remain visible in the uncertainty.

## Spatial blocking

Validation uses 500 m × 500 m blocks in EPSG:3157. A block is held out when
`sha256("p32-2026-11-05:" + block_id) % 4 == 0`. Held-out blocks are fixed before
sampling and are not changed after looking at results. No validation point may be within
100 m of a block boundary to avoid edge leakage.

## Validation design

### Held-out public trees

- Sample 1,000 live public trees from held-out blocks, stratified by local area.
- Match each sampled tree to a detected crown within 5 m; compute recall with a 95%
  Wilson interval.
- Report the missed-public count and the distribution of miss distances. Do not tune the
  5 m rule after seeing this sample.
- Report height and crown error only for public records with measured fields; do not
  impute a measured truth from the same allometric model.

### Independent UBC test

- Run the same fixed detector settings on the UBC 2021 CHM with the UBC inventory as an
  independent test.
- Report recall and height/crown error by species group and by inventory completeness
  class. Do not use UBC to tune city parameters.

### Manual orthophoto audit

- Draw 300 candidates from held-out blocks, stratified equally by confidence band
  (low < 0.5, medium 0.5–0.7, high ≥ 0.7) and by land proxy.
- Inspect the 2022 orthophoto at a fixed scale; label each candidate as tree, non-tree, or
  uncertain. Record the reason for each non-tree label.
- Compute precision with a 95% Wilson interval, including and excluding uncertain labels.
- Report precision separately for likely-private, street, park, and other/unknown proxies.

### Count and carbon uncertainty

- Report the candidate count as an interval from estimated precision and the unmatched
  public-tree miss rate; do not present a single-candidate count as a census.
- Propagate height, crown, and allometric error into a range for crown volume and carbon.
- Report the overlap problem: summed crown area is not unique canopy area.

## Sample sizes

- Recall: 1,000 public trees. At an expected 70–80% recall, the 95% Wilson half-width is
  about 2.7–3.0 percentage points.
- Precision: 300 candidates. At 50% precision, the 95% Wilson half-width is about 5.7
  percentage points; at 80%, about 4.5 points.
- UBC: all usable inventory records, with a minimum of 500 matched candidates or a stated
  shortfall.

If a sample is short, report the achieved sample and widen the interval; do not top it up
with non-held-out blocks.

## Error metrics

- Recall, precision, false-positive reasons, and missed-public reasons.
- Height: bias, MAE, and RMSE against measured public/UBC heights.
- Crown radius/area: bias, MAE, and correlation against measured crown width.
- Carbon and volume: interval from the allometric screening model, with species unknown.
- Count: point estimate plus interval, never a census claim.

## Privacy and exposure

Never expose or store in tracked outputs:

- owner names, mailing addresses, or private contact details;
- parcel-level ownership claims or a parcel identifier that resolves to an owner;
- private photos or field observations without consent;
- a statement that a candidate is on private property, only that its land-context proxy is
  `likely private parcel`.

Candidate coordinates, height, crown, confidence, and land proxy are public screening
evidence. The public tree inventory stays a separate layer.

## Compute and storage budget

- Detection: one 644 s sequential run on the local host for the 2 m CHM baseline.
- Candidate rebuild from cache: 158 s.
- Outputs: 14 MB detection cache, 11 MB compressed candidate GeoJSON, 1 KB summary.
- Storage root: `/srv/shared-data`; 7.7 TB free after the baseline build.
- No validation imagery or private data is written to the repository.
