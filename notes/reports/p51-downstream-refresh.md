# P51 downstream refresh from the corrected change screen

Status: corrected data products and docs complete; public API/UI remains on the original
P43 products pending P51.4 review.

## P38 source recovery

The standalone P38 `heat_priority.json` was absent from local processed data. P51 rebuilt
P38 from public Statistics Canada 2021 Census Profile files and the public dissemination-area
feature service:

- 1,068 DA features downloaded in the Vancouver bounding box;
- 1,035 DA features selected by the City boundary;
- 1,033 received an equity score;
- P38 build produced 870 400 m cells, of which the original 797 P42/P44 cell ids are
  retained for the downstream refresh;
- Census population represented: 673,655.

This is a fresh P38 rebuild, not a copy of the old P38 fields.

## Corrected downstream products

Output directory:

`data/processed/vancouver_2022_control/`

Products:

- `canopy_change.json` / `.geojson` / `.png`
- `canopy_action.json` / `.geojson` / `.png`
- `canopy_turnover.json` / `.geojson` / `.png`

### P44 action counts

| Action | Original P44 | Corrected |
| --- | ---: | ---: |
| plant + cool | 265 | **166** |
| monitor | 233 | **196** |
| expand canopy | 133 | **110** |
| structural shade | 127 | **113** |
| protect / investigate loss | 39 | **212** |

### P46 turnover

- High-tier cells: **259** (original 260).
- Total turnover area: **135.58 ha** (original 181.76 ha).

The shift toward `protect / investigate loss` follows from the corrected negative net
screen. It is a screen, not proof of loss; the P51 control sample and the P43
classification/co-registration limits still apply.

## API/UI status

The public API, map, and app continue to use the original P43/P44/P46 products. The
corrected sidecar products are versioned data outputs only at this stage. P51.4 must decide
whether to expose them and how to label the switch.

## Limits

- P38 rebuild uses public Census inputs but is restricted to the original 797-cell grid.
- P51 control is a 34-tile spatial sample with one western outlier.
- Corrected action/turnover labels are screening labels, not planting or survival claims.
- No final citywide net-loss claim.
