# ADR 0003: Use CHM-based detection and explicit repeat-measures change

Status: accepted
Date: 2026-11-03

## Context

Individual-tree detection is a crowded field. ForestTools, lidR, PyCrown, and itcSegment
implement variants of local maxima plus crown delineation, mostly under GPL. A hard
dependency would create a licence and maintenance bottleneck.

## Decision

- Build the CHM from the supplied DSM-DEM pair or from the highest return per DEM cell.
- Detect tree tops with a local-maximum filter and segment crowns with
  marker-controlled watershed (`scipy.ndimage`). Document this as a first-pass method.
- Report canopy change as a thresholded area comparison (gain, loss, stable, mean height
  change on stable canopy) rather than a single cover number.
- Keep point-cloud segmentation, Dalponte-style region growing, and QSM as future work.

## Consequences

- The method is readable, dependency-light, and testable.
- It is less accurate than a tuned point-cloud segmentation, especially in dense
  multi-layer stands and on steep terrain.
- Every change report must state the acquisition dates, leaf-on/leaf-off status, and the
  canopy threshold. A raw difference is not a growth estimate.
