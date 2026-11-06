# P32 attribute uncertainty

Date: 2026-11-06

Status: P32.5 screening implementation. This is not a field-calibrated private-tree
attribute model.

## Method labels

Every candidate now carries method-labelled point estimates and ranges:

| Attribute | Method | Evidence tier | Envelope |
| --- | --- | --- | --- |
| Height | ALS 2 m block-max CHM segment peak | LiDAR screening | ±20% |
| Crown radius | Watershed segment equivalent radius | LiDAR screening | ±25% |
| DBH | Height-to-DBH allometry, species unknown | Allometric screening | ±35% |
| Crown volume | Ellipsoid from CHM height and segment width | Allometric screening | ±50% |
| Carbon | Jenkins et al. above-ground biomass, species unknown | Allometric screening | ±50% |

The ranges are **screening envelopes, not calibrated confidence intervals**. They are
stored as `height_low_m`, `height_high_m`, `crown_radius_low_m`,
`crown_radius_high_m`, `dbh_low_cm`, `dbh_high_cm`, `crown_volume_low_m3`,
`crown_volume_high_m3`, `carbon_low_kg`, and `carbon_high_kg`.

`attribute_evidence` is `lidar_screening; allometric_unknown_species` for every candidate.

## Candidate totals

| Field | Low | Point estimate | High |
| --- | ---: | ---: | ---: |
| Height sum (m) | 3,145,113 | 3,931,391 | 4,717,667 |
| Crown volume (m³) | 303,236,475 | 606,472,619 | 909,709,127 |
| Carbon (kg) | 51,710,156 | 103,421,263 | 155,132,762 |

The point estimates are the existing allometric screening totals. The ranges are not a
measurement of uncertainty in a statistical sense; they show the planning envelope implied
by the stated factors.

## Public calibration check

Using one-to-one matches to measured public trees, the matched-public residuals were
wide and biased: height residuals p5/p95 were −3.49/+9.08 m, crown-width residuals
−6.66/+8.88 m, and DBH residuals −50.76/+10.90 cm. Those residuals mix detection centroid
error, inventory measurement, and allometric misspecification. I did not use them to narrow
the candidate envelopes; doing so would imply a calibration the data do not support.

## Limits

- Species is unknown for candidates; no species assertion is made.
- DBH, volume, and carbon are model values, not measurements.
- The ranges are not independent of the point estimates: low/high are fixed multipliers.
- Totals are candidate-table totals, not a total-city carbon inventory.
- Public/UBC calibration, species-group priors, and a defensible uncertainty model remain
  open before any public claim.
