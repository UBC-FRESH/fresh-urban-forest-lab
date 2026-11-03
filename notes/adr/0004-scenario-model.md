# ADR 0004: Scenarios are append-only edits over an immutable dataset

Status: accepted
Date: 2026-11-03

## Context

A planner needs to test planting, removal, replacement, and movement without corrupting a
baseline inventory. Commercial tools often use a mutable database with per-tree history;
that is more than a prototype needs.

## Decision

- Keep the dataset immutable.
- Represent a scenario as a base dataset id, an ordered tuple of typed edits, a projection
  horizon, and a revision number.
- Persist scenario JSON atomically.
- Reconcile year-zero scenario cover and volume with the raster baseline using an additive
  offset, so the scenario starts at the published canopy value.
- Use a transparent allometric growth model with crown-light-exposure adjustment.

## Consequences

- Every scenario is reproducible from its JSON.
- There is no destructive edit path.
- Concurrent edits are detected by revision, not silently merged.
- A future database can store the same edit records; the contract does not depend on the
  current file store.
- Growth is a scenario model, not a calibrated prediction. The UI must say so.
