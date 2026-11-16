# P71 street-tree ground-plane sanity gate

Status: complete. Squash-merged in PR #333 as `235ddc1`.

## Gate

A level-camera ground-plane check compares the observed ZoeDepth depth at the box bottom with
the expected ground range from an assumed camera height. The gate was tested at 2.0, 2.5, and
3.0 m with a depth/range interval of 0.5-2.0.

The gate does **not** improve the P69 semantic audit:

| Camera height | Supported candidates | Inventory matches ≤8 m | Bottom `tree` among gate-consistent audits | Among gate-inconsistent audits |
| ---: | ---: | ---: | ---: | ---: |
| 2.0 m | 7,405 (37.4%) | 2,325 | 40.7% | 44.8% |
| 2.5 m | 9,216 (46.6%) | 2,835 | 40.6% | 45.3% |
| 3.0 m | 10,844 (54.8%) | 3,218 | 37.8% | 47.8% |

A tighter 0.75-1.5 ratio at 2.5 m retained 5,360 candidates (27.1%); the audit-consistent
bottom-tree share was **37.2%**, lower than the inconsistent share of 45.5%.

## Interpretation

The gate rejects many candidates, but it does **not** select boxes with a higher chance of a
tree at the bottom centre. The likely reasons are:

- camera pitch is unmodeled;
- the assumed camera height is unknown;
- ZoeDepth depth is not necessarily the box-bottom surface;
- a building, vehicle, or facade can accidentally satisfy a ground-range ratio.

This is a negative result. The gate should not be integrated into the canonical layer or the
demo.

## Artifact

The diagnostic sample-only file (not recommended and not served) is:

`/srv/shared-data/gep/ws4/external/street_trees/p71_ground_gate_sample.geojson`

Machine-readable results: `notes/reports/p71-ground-gate.json` and
`notes/reports/p71-ground-gate-tight.json`.

## Limits

- Level-camera approximation only; no pitch calibration.
- No field validation, precision/recall, ownership, survival, or complete-census claim.
- Canonical 19,790-feature layer unchanged.
