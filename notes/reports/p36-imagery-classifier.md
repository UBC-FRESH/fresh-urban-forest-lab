# P36 GPU imagery classifier pilot

Date: 2026-11-06

Status: P36.1–P36.3 implemented; candidate application and close-out remain open.

Parent issue: #161

## Hardware

- NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition
- 97,887 MiB visible VRAM
- CUDA 13.2, PyTorch 2.14.1+cu130
- 72 CPU cores, 256 GiB RAM

## Imagery

- Source: City of Vancouver **Orthophotos 2022** ArcGIS tiled service
  `https://tiles.arcgis.com/tiles/qrcTTRTwUoS8N47o/arcgis/rest/services/Orthophotos_2022/MapServer`
- Zoom 19, approximately 0.30 m/pixel
- 96 × 96 RGB chips, balanced 6,000 conifer + 6,000 deciduous samples drawn from the
  Vancouver public inventory
- 12,621 orthophoto tiles cached; 249 MB chip cache; model 1.5 MB
- Orthophotos are orthorectified: no stereo claim.

Other public imagery:
- Burnaby 2025 orthophoto image service
- Surrey 2025 orthophoto tiles
- Coquitlam 2025 7.5 cm MrSID
Burnaby and Coquitlam still have no public species inventory.

## Model

- Four-block CNN with batch normalisation and adaptive pooling
- 96 × 96 RGB input; class-weighted cross-entropy
- 500 m spatial-block holdout
- 8,718 train chips / 3,282 held-out chips
- 20 epochs, batch 64, AdamW; ~49 s wall clock on the GPU

## Held-out results

| Metric | Value |
| --- | ---: |
| Accuracy | 80.04% (95% Wilson 78.64–81.37%) |
| Conifer precision | 84.41% (82.49–86.15%) |
| Conifer recall | 75.18% (73.06–77.18%) |
| Deciduous precision | 76.34% (74.31–78.26%) |
| Deciduous recall | 85.22% (83.39–86.88%) |
| Brier score | 0.1438 |

Confusion matrix:

|  | Predicted conifer | Predicted deciduous |
| --- | ---: | ---: |
| True conifer | 1,272 | 420 |
| True deciduous | 235 | 1,355 |

Compared with the P35 structural baseline, the image model trades some overall accuracy for
a large gain in conifer precision: P35 had 37.7% conifer precision at 79.9% conifer recall;
the image model has 84.4% conifer precision at 75.2% conifer recall. The image test is
balanced (50/50), while P35 was dominated by deciduous, so compare per-class metrics rather
than the headline accuracy alone.

### Valid LiDAR + image fusion

A second stack used only **independent CHM crown features** plus image probability:

- CHM features: max height, centre height, canopy fraction, crown area, p90 height, height
  std, centre/max ratio.
- Held-out fusion: **81.87% accuracy**, **82.63% conifer precision**, **82.09% conifer
  recall**.
- CHM-only: 70.02% accuracy; image-only: 80.04%.
- The earlier inventory-height/crown fusion was rejected as label leakage and is not used.

This is the valid fusion result shipped in the interface.

## What this proves

- Real orthophoto pixels are accessible without ArcGIS credentials.
- The GPU path is fast: a 12k-chip balanced pilot trains in under a minute after caching.
- The image signal is materially better for conifer precision than height/crown width alone.
- More data, fusion with LiDAR shape features, and transfer to Burnaby/Surrey/Coquitlam are
  now concrete next steps.

## Fusion diagnostic (not used)

A trial stack combining image probability with inventory height/crown fields produced an
implausible 100% held-out result. Those structural fields encode species-group assumptions
(crown ratio/height/crown allometry), so the fusion is invalid as an independent test. It
was removed rather than shipped. P36.3 needs LiDAR-derived crown/point features, not
inventory-derived attributes.

## Candidate image scoring (Burnaby pilot)

The image CNN was applied to Burnaby's high-confidence off-inventory candidates using the
public Burnaby 2025 orthophoto image service.

- 331,221 candidates scored (all candidates with confidence >= 0.6).
- Image model groups: 186,819 conifer, 144,402 deciduous.
- Candidate GeoJSON now carries `imagery_group`, `imagery_conifer_probability`,
  `imagery_source`, and `imagery_date`.
- The 3D candidate overlay uses the image group when present.
- No known-good accuracy is reported: Burnaby has no public species inventory.
- Vancouver candidate scoring and Surrey/Coquitlam imagery transfer remain open.

## Still open

- ~~Fuse image features with LiDAR point/CHM features (P36.3).~~ Completed with CHM-only + image fusion; raw point-cloud fusion remains an extension.
- Complete image scoring for Vancouver, Surrey, and Coquitlam candidates.
- Apply to Burnaby/Coquitlam imagery; both still lack known-good species labels.
- Complete the final P36 close-out.
- No stereo/photogrammetric claim: orthophotos alone are not a stereo pair.
