# P53 full 181-tile vertical control and corrected publication

Parent issue: #282
Planned branch: `feature/p53-full-control`
Status: active

## Why

P51 used a 34-tile spatial sample and found a near-zero vertical offset (+0.015 m),
changing the P43 screen from +223 ha to about −92.5 ha. The remaining limitation is that
34 of 181 tiles are not the full city.

P53 uses all 181 indexed 2018 tiles, tests spatial stability, and publishes the corrected
products as an explicit versioned layer.

## Scope

- Browser-download all missing 2018 tiles; verify indexed SHA-256.
- Run class-2 ground control against the 2022 DEM on every tile.
- Estimate constant versus per-tile correction; report spatial variation and uncertainty.
- Regenerate corrected P43, P44, and P46 products.
- Publish the corrected products as a selectable versioned layer; do not silently replace
  the original products.
- Add API/UI product labels and docs only if the full control is stable.
- Preserve P45/P50/P51 caveats where still relevant.

## Out of scope

- Field validation or survey-grade accuracy claims.
- A final citywide net-loss/gain claim without the full control result.
- Ownership, survival, planting, or causal claims.
- Unrelated scenario/product work.

## Gate

Proceed to publication only if the full-tile control is stable:

- at least 90% of contributing tiles within ±0.15 m of the sample median;
- no spatial trend larger than 0.10 m across the city;
- checksum-complete tile coverage or explicit missing tiles;
- no single outlier controls the sign.

If the gate fails, stop at a full control report and retain the prior warnings.

## Tasks

- P53.1 Full tile sample and control estimate.
- P53.2 Corrected P43/P44/P46 products.
- P53.3 Versioned API/UI publication and docs.
- P53.4 Browser/dashboard verification and close-out.

## Data handling

- Raw tiles stay under `/srv/shared-data`; manifests record checksums and URLs.
- Downloaded data and generated products are not committed.
- The original P43/P44/P46 products remain intact.
