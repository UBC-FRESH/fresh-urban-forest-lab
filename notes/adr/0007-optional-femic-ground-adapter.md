# ADR 0007: Optional FEMIC ground adapter is a sidecar contract

Status: accepted
Date: 2026-11-04
Issues: #95, #97, #98

## Context

P14 validated the PTD-inspired ground classifier on a coastal and a steep LidarBC tile.
P14.3 approved an optional FEMIC adapter prototype but did not approve a default pipeline
change. FEMIC is a separate lab system with its own release cadence, product contracts, and
default LidarBC path. This repository's rule is no hard dependency on another lab system.

## Decision

- The adapter is an **optional sidecar contract**, not a FEMIC core import and not a default
  product.
- The adapter writes `ground.laz`, `manifest.json`, and `qa.json` for one tile.
- The bundle schemas are `femic.ground-bundle.v1` and `femic.ground-qa.v1`.
- The adapter records the input/output hashes, CRS, vertical datum, parameter hash, method
  provenance, warnings, and QA fields.
- FEMIC may read the bundle later through a separate optional reader. That reader needs its
  own design and approval.
- The classifier remains opt-in. No `build`, `serve`, or default dataset path changes.

## Consequences

- The bundle is useful without FEMIC and can be validated on its own.
- FEMIC does not inherit the classifier's dependencies or warnings.
- The adapter adds a schema and a contract-test surface that must be versioned.
- A future FEMIC reader can be added without reopening the classifier design.
- The adapter is still a prototype; a manual reference patch and a full terrain suite are
  still missing.

## Alternatives considered

- **Put the classifier in FEMIC core.** Rejected: it couples release cadence, adds a hard
  dependency, and changes the default product path before the evidence is strong enough.
- **Write a FEMIC plugin now.** Rejected: the FEMIC-side plugin surface is not designed yet.
  A sidecar contract is the smallest safe boundary.
- **Only document the method and write no adapter.** Rejected: a concrete bundle contract is
  needed to test whether the output is useful to a consumer.
- **Write a Parquet-only sidecar.** Deferred: a LAZ copy keeps the point geometry and
  attributes in one LAS-native file; Parquet can be added later if tabular joins dominate.
