# P60 independent control for western vertical-control tiles

Parent issue: #310
Branch: `feature/p60-independent-control`
Status: active

## Goal

Test whether the four western P53 outlier tiles are supported by an independent public
vertical reference. The current decision is a constant **+0.011 m** correction with a
documented western-outlier caveat. This phase may retain that decision, refine it, or
return an inconclusive result.

## Target tiles

Tile names use 1 km UTM Zone 10 coordinates:

| Tile | Easting | Northing |
| --- | ---: | ---: |
| `4830E_54530N` | 483000-484000 | 5453000-5454000 |
| `4840E_54520N` | 484000-485000 | 5452000-5453000 |
| `4840E_54530N` | 484000-485000 | 5453000-5454000 |
| `4840E_54540N` | 484000-485000 | 5454000-5455000 |

Adjacent inlier tiles are comparison controls, not substitutes for independent evidence.

## Candidate independent references

- ICESat-2 ATL08 land-vegetation height and ATL03 geolocated photons.
- GEDI L2A elevation and height.
- Stable roof or road references only when tied to a documented independent elevation.
- Provincial or geodetic benchmarks if licence and datum are documented.

The class-2 ground proxy used in P53 is not independent and cannot decide this question by
itself.

## Feasibility gate

Stop and document an inconclusive result if:

- no external samples overlap the four tiles;
- the external vertical datum cannot be tied to the 2018 CGVD28GVRD and 2022 surfaces;
- footprints are too sparse or too uncertain to distinguish a local offset from noise;
- data access, licence, or lineage cannot be documented.

An inconclusive result must retain the existing constant correction and caveat.

## Tasks

- P60.1: Confirm bounds, search external archives, document access/licence/datum, and make
  the go/no-go decision.
- P60.2: If the gate passes, extract independent ground/height samples and compare offsets
  with the P53 class-2 control on the four outliers and adjacent inliers.
- P60.3: Record the decision, update docs/products only if supported, run the dashboard,
  open a PR, and close out.

## Acceptance

- Tile bounds and projections are reproducible.
- External data access, licence, version, and vertical datum are named.
- Sample counts, spatial coverage, and uncertainty are reported.
- The decision is explicit: retain constant correction, apply a local correction, or
  remain unresolved.
- No field-validation, citywide net-change, ownership, survival, or causal claim is added.
