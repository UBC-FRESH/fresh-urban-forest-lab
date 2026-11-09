# P55 vertical-control outlier adjudication and release

Parent issue: #294
Planned branch: `feature/p55-outlier-adjudication`
Status: pr-open

## Why

The full P53 control sample passes only after excluding four western tiles from the
stability gate. Those tiles have broad class-2 ground differences and may represent real
local ground change, classification effects, or a local vertical offset. P55 decides whether
the constant correction remains defensible and finalizes the release.

## Scope

- Inspect the four outlier tiles and their distributions.
- Compare adjacent inlier tiles and candidate stable surfaces.
- Decide constant correction versus local correction.
- Update corrected products only if warranted.
- Update docs/final verification and close the release.

## Out of scope

- New field work or survey-grade claims.
- Final citywide net-loss/gain claim without support.
- Ownership, survival, planting, or causal claims.

## Tasks

- [ ] P55.1 Outlier tile adjudication
- [ ] P55.2 Control-model decision and product update if warranted
- [ ] P55.3 Docs, final verification, PR, and close-out

## Decision rule

If the outliers are broad or cannot be tied to a stable surface change, retain the full
constant offset and the P53 caveat. Do not invent a local correction from four tiles.
