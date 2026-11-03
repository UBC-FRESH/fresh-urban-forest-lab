# ADR 0001: Seed this repository from the UBC-FRESH dev workflow

Status: accepted
Date: 2026-11-03

## Context

The lab already maintains a dev workflow seed: phase/task planning, a green dashboard, a
workflow validator, agent contracts, Sphinx docs, and GitHub issue conventions. Rebuilding
those surfaces would be wasteful and would produce a second, divergent process.

## Decision

Create `UBC-FRESH/fresh-urban-forest-lab` from `ubc-fresh-dev-workflow` and keep the
seed's contract. Adapt the planning surfaces and add project-specific domain rules, but do
not replace the dashboard, validator, or phase model.

## Consequences

- Every commit is checked by the same gates as the rest of the lab.
- New contributors and agents get the same session protocol.
- The project inherits the seed's documentation-first bias, which is appropriate for a
  method-heavy public-data project.
- Domain rules must stay in this repository's `AGENTS.md` and docs, not leak into the seed.
