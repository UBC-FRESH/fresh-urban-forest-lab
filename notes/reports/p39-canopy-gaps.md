# P39 canopy gaps and above-ground planting opportunity

Status: active. This is an above-ground screening layer, not a planting plan.

## What it does

The screen starts from the public 2022 LiDAR canopy surface and removes:

- existing canopy at 2 m or taller;
- building footprints;
- water;
- road surfaces, using a 3 m buffer around public OSM road centrelines;
- slopes steeper than 15°; and
- pixels outside the P38 scored 400 m cells.

The remaining open ground is split into:

- **edge gap** — open ground within 15 m of existing canopy;
- **street-adjacent gap** — edge gap within 10 m of a road centreline; and
- **interior open** — open ground farther than 15 m from canopy.

Contiguous edge gaps at least 45 m² are counted as one site. A gross crown-slot
envelope divides gap area by the small, medium, and large crown areas used in the
published CanopyFit scenario (13.2, 45.4, and 183.9 m²). This is an upper bound if
every square metre were available; it is not a tree count.

## Inputs

| Input | Source | Role |
| --- | --- | --- |
| 2022 DEM, CHM, building mask, water mask | City of Vancouver LiDAR / P30 processed dataset | Open-ground and gap masks |
| OSM road centrelines | © OpenStreetMap contributors, ODbL 1.0 | Road-surface exclusion and street adjacency |
| P38 heat-priority cells | `heat_priority.json` | Shade deficit, equity score, priority class |

## Vancouver result

Run at 5 m with the P30 Vancouver 2022 dataset and P38 cells:

- 797 populated 400 m cells.
- Open ground: 6,532.97 ha, 41.3% of the raster.
- Edge gap: 1,845.99 ha, 11.7% of the raster.
- Street-adjacent gap: 859.37 ha, 46.6% of edge gap.
- Interior open: 4,686.98 ha.
- Contiguous gap sites at least 45 m²: 69,861; street-adjacent: 52,670.
- Gross small-crown upper bound: 1,397,060; medium: 406,321; large: 99,961.
- Opportunity tiers: high 264, medium 263, low 263, none 7 cells.

The capacity numbers are deliberately not presented as a planting target. The
same gap area includes lawns, yards, park turf, parking-lot edges, and other open
ground where ownership, access, utilities, soil, irrigation, and maintenance are
unknown.

## Products

Generated under `data/processed/vancouver_2022/`:

- `planting_opportunity.json` — full 400 m cell records and metadata;
- `planting_opportunity.geojson` — WGS84 cells;
- `planting_opportunity.png` — transparent tier grid;
- `planting_opportunity_meta.json` — methods, thresholds, summary, and caveats.

The API exposes `/api/planting-opportunity` and
`/api/planting-opportunity.geojson` only when the product exists. The map has a
**canopy gaps** toggle and a sidebar summary.

## Reproduce

```bash
python scripts/build_vancouver_planting_opportunity.py \
  --root data/processed/vancouver_2022 \
  --heat-priority data/processed/vancouver_2022/heat_priority.json \
  --out data/processed/vancouver_2022 \
  --resolution 5 \
  --cell-size 400 \
  --slope-max 15 \
  --gap-distance 15 \
  --street-distance 10
```

## Limits

- **No utility conflicts.** Underground and overhead utilities are not public
  city-wide layers and are not modelled.
- **No ownership or access.** A gap is not permission to plant on private land.
- **No soil, irrigation, maintenance, or cost.**
- **No field validation.**
- **Road-adjacent is a proxy.** A road centreline buffer is not a confirmed public
  boulevard or planting strip.
- **Capacity is an upper bound.** It uses crown-area division without packing,
  access, or utility set-backs.
- **The P38 shade/equity join is optional.** Without it the score uses a neutral
  need value.
