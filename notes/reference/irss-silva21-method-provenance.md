# IRSS and Silva21 method provenance for urban LiDAR canopy work

Status: reference note, 2026-11-04
Scope: `fresh-urban-forest-lab`
Related: `UBC-FRESH/irss-expansion`, `UBC-FRESH/fresh-irss-demo`

## Short answer

The urban lab implements LiDAR canopy analysis, but the current repository does **not**
record it as an IRSS or Silva21 integration.

The implemented methods are generic and independently written:

- CHM from a DSM/DEM pair or the highest return per cell;
- local-maxima tree tops plus marker-controlled watershed crowns;
- canopy cover, height-field canopy volume, and height percentiles;
- off-inventory crown matching;
- thresholded repeat-measure canopy change; and
- 2D/3D canopy visualization.

The lineage is documented in:

- `notes/adr/0003-lidar-and-change-methods.md` — CHM/ITD method and limits;
- `notes/adr/0006-clean-room-method-reuse.md` — Arbor method mining, no code copying;
- `README.md` — design lineage names FEMIC, FHOPS, WS4, and fresh-fvsbc;
- `docs/reference/research-agenda.rst` — the urban programme's own literature anchors.

There is no `IRSS`, `Silva21`, Coops, Tompalski, or Wulder reference in the tracked
`README.md`, `docs/`, `notes/`, or `src/` text, and the IRSS expansion registry does not
name the urban lab as a target. The urban theme was screened out of the IRSS mine in
[`00-source-inventory.md`](https://github.com/UBC-FRESH/irss-expansion/blob/main/notes/00-source-inventory.md).

This note therefore records **method affinity**, not a completed integration.

## What is actually implemented

| Capability | Urban implementation | Method source | IRSS/Silva21 status |
| --- | --- | --- | --- |
| CHM | Highest return per DEM cell or supplied DSM-DEM | `src/fresh_urban_forest/lidar.py` | Generic; no IRSS code |
| Individual-tree detection | Local maxima + marker-controlled watershed | `src/fresh_urban_forest/itd.py`; ADR 0003 | Generic; ForestTools/lidR/PyCrown named as prior art |
| Canopy cover | CHM threshold and valid-cell area | `src/fresh_urban_forest/metrics.py`, `city_metrics.py` | Generic; not an IRSS contract |
| Canopy volume | Height-field prism at landscape level; ellipsoid crowns at tree level | `metrics.py`, `city_metrics.py` | Generic; no IRSS contract |
| Repeat-measure change | Thresholded gain/loss/stable comparison | `change.py`, `change_product.py`; ADR 0003 | Generic; not `DIS-01` |
| Off-inventory canopy | Detect, match, score unmatched crowns | `off_inventory.py`; P9 report | Independent method, not an IRSS candidate |
| Tree-level 2D/3D | MapLibre and Three.js scenes | `service.py`, web assets | Urban-specific |

The clean-room rule in ADR 0006 is important: methods may be mined from permissive or
copyleft references, but the implementation must be original and cited. That is the right
posture for future IRSS method reuse too.

## Candidate map

These are **candidates for evaluation**, not integrations already present. A candidate
moves forward only after a small test on the urban data and a provenance note.

| Candidate | Why it might fit | Fit risk | Proposed first step |
| --- | --- | --- | --- |
| `INV-02` tree-list and stem-distribution metrics from high-density LiDAR | The urban lab already detects crowns and wants tree lists; high-density drone/mobile LiDAR could improve DBH, competition, and stem maps | Current urban source is mainly 1 m CHM and city LiDAR, not dense TLS/MLS; forest tree-list assumptions do not transfer directly to open-grown urban trees | Compare one urban AOI against the `INV-02` contract and report which fields are measurable and which are not |
| `INV-06` structurally guided sampling with sgsR | Urban field validation is expensive; structure-guided plot or audit placement could improve coverage | The urban lab's field packet is already designed around canopy and allometry; sgsR is forest-plot oriented | Test a structure-guided selection on the existing UBC field packet before adding code |
| `BIO-02` forest structure habitat index | The urban lab already computes canopy structure and bird-habitat metrics; a structure index could make the comparison explicit | The Coops index is forest-stand oriented; urban open-grown crowns and buildings change the interpretation | Run the index on the urban CHM and compare it with the existing bird-habitat structure metrics |
| `DEC-04` EFI model card | The urban lab has evidence tiers and allometry but no single model-card surface for ITD, allometry, and canopy metrics | A forest EFI card does not map one-to-one to urban individual-tree detection | Prototype a narrow provenance card for the ITD and allometry outputs, using `DEC-04` as a shape reference |
| `DATA-01` uncertainty propagation | Canopy volume, carbon, and allometry are uncertain; the lab already labels evidence tiers | The forest curve-residual method does not fit all urban metrics | Attach uncertainty to one urban metric first, not to every output at once |
| `INV-01` ALS area-based inventory | Canopy height and cover are already CHM-derived; ABA could provide a comparison surface | Urban tree-level decisions need individual crowns; ABA is the wrong primary unit | Use as a comparison, not a replacement for ITD |
| `DIS-01` disturbance event schema | Repeat-measure canopy change could become a shared event record | The urban change product is a raster comparison, not a disturbance event catalog | Defer until there is a real loss/event use case |

## Proposed integration sequence

1. **Keep the current method lineage visible.** This note and ADR 0003/0006 are the
   baseline. Do not describe the existing CHM or ITD work as IRSS-derived.
2. **Evaluate `INV-02` and `INV-06` first.** They have the clearest connection to urban
   tree lists and field validation. A test on one AOI is enough to decide whether to
   pursue either.
3. **Evaluate `BIO-02` against the existing bird-habitat metrics.** Reuse only if the
   index adds a decision-relevant distinction that the current canopy metrics do not.
4. **Adapt `DEC-04`/`DATA-01` narrowly.** A provenance card for ITD/allometry and
   uncertainty on one canopy metric are more useful than a broad contract transplant.
5. **Do not add `fresh-urban-forest-lab` to the IRSS registry as a target without a
   registry decision.** The current registry target set is `femic`, `ws3`, `ws4`,
   `fhops`, and `nemora`; a related app is not automatically a target.

## Copied or reused?

Nothing from the IRSS/Silva21 candidate set is currently copied or vendored here. The
current code uses:

- public LiDAR and tree-inventory data;
- generic published methods reimplemented in Python; and
- evidence tiers and provenance patterns from the FRESH workflow.

If a future change copies code or a schema from another project, follow ADR 0006 and add
the source, licence, and a failing test before the integration is claimed.

## Sources checked

- `UBC-FRESH/irss-expansion` registry:
  <https://github.com/UBC-FRESH/irss-expansion/blob/main/registry/candidates.yaml>
- IRSS/Silva21 source scope and screening:
  <https://github.com/UBC-FRESH/irss-expansion/blob/main/notes/00-source-inventory.md>
- Current repo-state check:
  <https://github.com/UBC-FRESH/irss-expansion/blob/main/notes/10-repo-state-check.md>
- Urban method decisions:
  `notes/adr/0003-lidar-and-change-methods.md`,
  `notes/adr/0006-clean-room-method-reuse.md`
- Urban data and limitations:
  `docs/reference/vancouver-city-pilot.rst`,
  `docs/reference/limitations.rst`,
  `notes/reports/p9-off-inventory.md`
