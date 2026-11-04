# Software landscape and borrowed design patterns

Status: reference note, 2026-11-03.

This note records the scan of comparable urban-forest inventory, canopy, LiDAR, growth,
and decision-support systems. The rule is **no hard dependency on a system we do not
control**. We reimplement the method or interface we need in this repository, keep the
licence clean, and record what we deliberately did not copy.

## Scope of the scan

- municipal tree inventory and work-order platforms;
- open-source crowdsourced tree maps;
- i-Tree methods and allometric equations;
- airborne LiDAR individual-tree detection and segmentation;
- urban tree growth and allometry;
- street-level green-view and canopy-change methods;
- 3D landscape and tree rendering.

## What exists, and what is safe to reuse

| Project or product | What it does well | Licence / access | Reuse decision | What we took or avoided |
| --- | --- | --- | --- | --- |
| **OpenTreeMap 2** (`OpenTreeMap/otm-core`, `otm-ecoservice`) | Crowdsourced tree and planting-site inventory, per-tree edits, public map, CSV/KML export, i-Tree Streets benefit lookup, mobile clients. | AGPL-3.0. Strong copyleft; network use triggers source disclosure. | **Design pattern only.** Do not copy code into this MIT repository. | We adopted the separation of a **tree** from a **planting site**, the idea of an append-only edit history, and a public read-only map. We did not adopt the Django/PostGIS stack, the AGPL code, or a hard i-Tree dependency. |
| **TreeKeeper** (Davey) | Deep municipal inventory, work orders, 311/Cartegraph/Cityworks integrations, public guest view, ecosystem benefits, unpublished risk forms. | Commercial, per-tier licence. | **Feature benchmark only.** | Confirms the minimum operator surface: inventory, work history, work orders, risk, public map, exports. Our prototype stops at inventory + scenario + DSS and records work orders as future scope. |
| **TreePlotter INVENTORY / JOBS** (PlanIT Geo) | GIS-first inventory, offline field collection, configurable queries, i-Tree benefits API, add-on work orders and risk. | Commercial, quote-based. | **Feature benchmark only.** | Confirms the value of a map-first UI, attribute filters, saved views, and an export path. We made the map and scenario editor the centre of the prototype. |
| **ArborPro / ArborScope / ArborStar / Ezytreev / R3 GreenSpaces** | Mature inventory, work order, risk, and field collection workflows. | Commercial. | **Feature benchmark only.** | Reinforces the need for a stable data contract and a versioned import/export rather than a bespoke schema per vendor. |
| **i-Tree Eco / Streets / Design** | Peer-reviewed urban forest structure and ecosystem-service methods; field variables; biomass equations; growth adjustment by condition and crown light exposure; benefit transfer. | USDA Forest Service public domain / freeware; some resources are EULA-governed. | **Method reimplementation, not code reuse.** | We implemented a transparent diameter-based biomass model after Jenkins et al. (2003), above-ground carbon as half of biomass, crown-light-exposure growth adjustment, and a scenario timeline. We did not copy i-Tree code or claim i-Tree equivalence. |
| **Urban Tree Database** (McPherson, van Doorn, Peper 2016, PSW-GTR-253) | 365 equation sets for 171 species in 16 US climate regions; age to DBH, DBH to height/crown/leaf area; biomass factors. | US Government work, public domain. | **Data and equation source, not a code dependency.** | Our growth model uses the same conceptual structure (size-dependent increment that declines toward an asymptote), but uses transparent generic profiles until a BC/Vancouver calibration is fitted. The database is the preferred next calibration source. |
| **carboncalc** (`adhollander/carboncalc`) | Individual urban-tree biomass and growth from the Urban Tree Database, SQLite-backed, REST API and Shiny prototype. | Public domain. | **Method reference.** | Confirms the value of a versioned species/equation database. We keep coefficients in code and record the source in the model note; a data-driven coefficient table is a Phase 5 extension. |
| **allometree** (R) | Fits and selects height–diameter and crown allometries, including multi-species and mixed models. | Open source R package (check current licence on CRAN/GitHub). | **Method reference.** | Informs the model-fitting roadmap: fit local equations from repeat inventory measurements rather than assuming generic curves forever. |
| **ForestTools** (R) | Variable-window filter tree detection plus marker-controlled watershed crown segmentation on a CHM; GLCM texture metrics. | GPL-3. | **Algorithm reimplementation.** Do not copy GPL code. | We implemented local-maxima detection and marker-controlled watershed segmentation from the published method in `src/fresh_urban_forest/itd.py`. No R dependency. |
| **lidR** (R) | Rich LAS/LAZ processing, CHM/DTM, point-cloud and raster ITD/ITS algorithms, LAScatalog processing. | GPL-3. | **Algorithm and vocabulary reference.** | We borrowed the CHM → local maxima → watershed sequence and the separation of detection from segmentation. We did not copy code or add an R dependency. |
| **Arbor** (`r-lidar/arbor`) | MLS/TLS pipeline: hybrid decimation, ground/HAG, wood likelihood, semantic and instance segmentation, QSM/QSF, quality codes. | GPL-3.0. | **Method and design-pattern reference only.** Do not copy code into this MIT repository. | We reimplemented hybrid homogenization, SOR, sparse voxel components, kNN anisotropy, and a simplified PTD-inspired ground classifier from the book's method descriptions in `pointcloud.py`. We did not copy Arbor code, vendor its C++, or import the MLS pathfinder/QSM stack. See `notes/reference/arbor-method-mining.md`. |
| **PyCrown** | Fast raster ITD with local maxima and Dalponte–Coomes crown growth; DSM/DTM handling on steep terrain. | GPL-3; repository archived. | **Algorithm reference only.** | Confirms the need for terrain correction and a circular/region-growing crown option. Our first implementation is simpler and documented as such. |
| **itcSegment** (R) | Published individual-tree crown delineation with adaptive windows and region growing. | GPL. | **Algorithm reference only.** | Same family as ForestTools/PyCrown. We cite the method family and avoid code reuse. |
| **Treepedia / Treepedia 2.0** (MIT Senseable City Lab) | Street-level Green View Index from Google Street View; Otsu/mean-shift and deep-learning segmentation; open city results. | BSD-2-Clause for the original code; model weights and images have separate terms. | **Metric and UX reference.** | We did not implement GVI because it needs proprietary Street View imagery. The idea is recorded as a future street-level layer, not a core dependency. |
| **PDAL / Open3D / WhiteboxTools / QGIS / GRASS** | Point-cloud processing, 3D geometry, geospatial analysis, GIS desktop. | BSD/MIT/GPL mix. | **Toolchain reference.** | We use `laspy`, `rasterio`, `pyproj`, `shapely`, and `scipy`, all permissively licensed, and keep PDAL/QGIS as optional operator tools rather than runtime dependencies. |
| **Vancouver street-tree dashboards** (MountainMath, R Shiny examples) | Public exploration by species, size, neighbourhood, and map. | Mixed open licences; data under OGL-Vancouver. | **UX reference.** | Confirms that species/size filters, a map, and a compact inspector are the highest-value first screen. |

## Patterns adopted in this repository

1. **Tree and planting site are different objects.** A planting site can exist before a
   tree does, and a site can be replanted. This prototype keeps a `TreeRecord.status` and
   an append-only `ScenarioEdit` log; a first-class `PlantingSite` entity is the next
   schema change, not a rewrite.
2. **The edit log is the history.** Every scenario change is a typed edit with an id and a
   note. A scenario is a base dataset plus ordered edits plus a projection horizon. This
   is the smallest useful version of OpenTreeMap's per-tree history without a database.
3. **Read-only public view, writable scenario layer.** The baseline dataset is immutable;
   scenarios live in `runtime/scenarios/` and are versioned with a revision number. This
   mirrors the public map plus staff-edit split in commercial tools.
4. **Map first, table second.** The 2D map is the primary navigation surface; the tree
   inspector and scenario cards are secondary. This matches the strongest products in the
   scan.
5. **Exports are first-class.** Every scenario can be exported as GeoJSON and as a CSV
   timeline. TreeKeeper/TreePlotter buyers consistently cite data exit as a requirement.
6. **Benefits are estimates with a named method.** Carbon is not a black-box i-Tree value.
   The model note records the equation family, the assumptions, and the fact that this is
   not a calibrated i-Tree replacement.
7. **Local maxima plus watershed, not a black box.** The LiDAR tree detection is a small,
   readable implementation of a published method. It is deliberately not a dependency on
   a GPL R package or an archived Cython project.
8. **Offline-capable front end.** MapLibre and Three.js are vendored; the 2D basemap is a
   local hillshade and canopy raster, not a tile service. The prototype works on a field
   laptop with no external network.

## Deliberately out of scope for the prototype

- work orders, crew scheduling, and 311/asset-management integrations;
- risk assessment forms (ISA/QTRA) and appraisal;
- user accounts, roles, and a hosted multi-tenant service;
- a full i-Tree Eco benefit-transfer engine;
- species identification from imagery;
- terrestrial laser scanning and quantitative structure models;
- a calibrated BC urban growth model.

These are recorded so that the next phase can pick them up without pretending the current
prototype already has them.

## Method references to keep

- Jenkins, J.C., Chojnacky, D.C., Heath, L.S., Birdsey, R.A. (2003). *National-scale
  biomass estimators for United States tree species.* Forest Science 49(1): 12–35.
- McPherson, E.G., van Doorn, N.S., Peper, P.J. (2016). *Urban tree database and
  allometric equations.* USDA Forest Service PSW-GTR-253.
- Nowak, D.J. (2021, 2024). *Understanding i-Tree: summary of programs and methods.*
  USDA Forest Service NRS-GTR-200.
- Dalponte, M., Coomes, D.A. (2016). *Tree-centric scanning of forest and woodland
  areas from airborne laser scanning data.* Remote Sensing 8(12): 1030.
- Li, X., Zhang, C., Li, W., Ricard, R., Meng, Q., Zhang, W. (2015). *Assessing
  street-level urban greenery using Google Street View and a modified green view index.*
  Urban Forestry & Urban Greening 14(3): 675–685.
- City of Vancouver (2022). *2022 Vancouver tree canopy assessment.*
- UBC SEEDS / UFOR 220 (2024). *UBC Vancouver campus tree inventory* reports and toolkit.
- Roussel, J.-R. (2026). *Arbor: Tree Segmentation in MLS/TLS Point Clouds* (version
  1.1.5) [Computer software]. https://github.com/r-lidar/arbor
- Roussel, J.-R. (2026). *Arbor: The Complete R Tutorial Book*.
  https://r-lidar.github.io/arbor_book/
- Axelsson, P. (2000). *DEM generation from laser scanner data using adaptive TIN
  models.* International Archives of Photogrammetry and Remote Sensing, 33(B4/1),
  110–117.

## Next scan targets

- Open source mobile field-collection stacks (QField, ODK, KoboToolbox) for offline
  inventory and photo capture;
- BC LiDAR change-detection studies and the provincial LiDARBC quality levels;
- urban heat and shade modelling (SOLWEIG, Radiance) for a future ecosystem-service layer;
- open 3D tree libraries that support instancing and level of detail at city scale.
