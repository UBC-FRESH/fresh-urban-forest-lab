# P51 citywide vertical control

Status: P51.1 complete; corrected-product work pending.

## Sample

- Deterministic rule: one smallest 2018 ZIP per populated 6 × 6 longitude/latitude bin,
  restricted to tile centres inside the P43 city bounds.
- Selected: **34 tiles**, **13.1 GB**; 5 reused from P50, 29 downloaded via the headful
  browser path.
- All downloaded ZIPs matched the indexed SHA-256.
- 31 tiles contributed class-2 ground observations; three had no usable control points.

## Control estimate

- Retained paired observations: **196,943**.
- Median 2018-ground minus 2022-DEM offset: **+0.015 m**.
- MAD: **0.053 m**.
- Interquartile range: **−0.048 to +0.061 m**.
- Bootstrap 95% interval: **+0.013 to +0.016 m**.
- Per-tile medians: **−0.430 to +0.053 m**.
- **30 of 31** tiles are within ±0.15 m of the sample median.
- One western tile is a −0.43 m outlier. Excluding it, the easting trend is about
  **−0.01 m** across the sampled longitude range; including it, the fitted easting trend is
  about **+0.11 m**. The north-south trend is about **−0.08 m**.
- No class-6 roof control: the sampled 2018 LAS classes do not contain class 6. No
  unclassified roof proxy was used.

## Gate decision

**Conditional pass.** The median and 30/31 tile consistency support a constant offset of
about **+0.015 m**, not the P43 **+1.0 m** assumption. The western outlier and the lack of a
citywide probability design are retained as caveats. Do not replace the constant estimate
with an unvalidated per-tile correction.

## P43 effect

P43 added +1.0 m to the 2022 DEM when it stood in for 2018 ground. The measured correction
to the P43 earlier surface is:

```text
1.0 - 0.015 = +0.985 m
bootstrap range: +0.984 to +0.987 m
```

The corrected 2 m screen is about **−92.5 ha** (range **−93.6 to −92.2 ha**), compared with
the P43 **+223 ha**. The sign is negative across the control interval, but this remains a
corrected screen, not a final citywide net-loss claim.

## Limits

- Not a probability sample of all 181 tiles.
- Ground can be excavated, filled, or reclassified.
- One western tile is a spatial outlier.
- Classification, co-registration, scale, edge, and acquisition-season effects remain.
- Not survey-grade accuracy control or field validation.
