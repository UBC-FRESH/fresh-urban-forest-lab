# Observed canopy change: UBC core, same 2 km mask

Status: three products on a common mask, 2026-11-03.

## Common mask

All three comparisons use the same projected 2 km × 2 km core box
`E481000–E483000, N5456000–N5458000` and a 1 m grid. This removes the coverage
difference that made the earlier products hard to compare.

## Results

| Comparison | Earlier canopy | Later canopy | Gain | Loss | Net | Mean height change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| UBC 2015 → LidarBC 2016 | 2.359M m² | 2.347M m² | +175,360 m² | −187,376 m² | **−12,016 m²** | −0.095 m |
| UBC 2015 → UBC 2021 | 2.359M m² | 2.470M m² | +320,535 m² | −209,369 m² | **+111,166 m²** | +0.235 m |
| LidarBC 2016 → UBC 2021 | 2.347M m² | 2.470M m² | +263,201 m² | −140,019 m² | **+123,182 m²** | +0.420 m |

Valid overlap is 4.00M m² for every comparison.

## Interpretation

- The 2015→2016 comparison is nearly balanced (−12k m² net). This is the right sanity
  check: two independent one-year-apart acquisitions should not show a large systematic
  gain or loss.
- The 2015→2021 and 2016→2021 comparisons both show a net gain of about 110–123k m² over
  five to six years.
- The difference between the two multi-year products is modest compared with the
  difference from the one-year product, which is reassuring.
- The mean height change is small (+0.24 to +0.42 m) relative to the height RMSE of the
  detection validation. Do not treat it as a precise growth rate.

## Caveats

- 2015 is EPSG:26910 and was transformed to the 2021 EPSG:3157 grid before binning.
- Vertical datums and acquisition seasons differ.
- The canopy threshold is 2 m.
- A canopy gain is not proof of planting; it can reflect growth, crown expansion, better
  returns, or a method difference.
- Loss can reflect removal, dieback, pruning, shadow, or a lower-quality return.
- The products are screening surfaces, not a calibrated growth model.

## Next

1. Add a field-verified complete-reference patch.
2. Collect repeat DBH measurements for growth calibration.
3. Add City 2018↔2022 if the tile host can be fetched.
4. Use the same-mask approach for any future city or regional comparison.
