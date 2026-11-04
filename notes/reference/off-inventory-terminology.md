# Off-inventory canopy: terminology, privacy, and data governance

Status: P9.1 method note, 2026-11-04.

## Terminology

Use **off-inventory urban trees** for the operational layer: trees that are visible in
remote sensing but do not match a record in the official inventory.

Related terms:

- **private-property canopy** when ownership is the point;
- **trees outside formal inventory** for a policy audience;
- **trees outside forests (TOF)** only when using the FAO/forest-inventory definition;
- **unmatched detected crown** for the raw LiDAR object before any confidence or land
  class is assigned.

**“Shadow urban forest” is a communication nickname, not an established scientific
term.** “Shadow inventory” already means unsold or off-market housing in real estate. Do
not use it in a paper, dataset field, API name, or policy claim without defining it.

## What the layer is

The layer is a separate, joinable population:

- official inventory records stay unchanged;
- candidates have stable `off:<candidate_id>` identifiers;
- candidates carry `confidence`, `land_class`, and `nearest_inventory_m`;
- candidates are not valid until a field or imagery check confirms them;
- the spatial layer is a screening surface, not a census.

## Land class

The pilot has no parcel layer. It uses:

- **inside analysis boundary (ownership unknown)** when the candidate falls inside the
  project boundary;
- **outside analysis boundary (ownership unknown)** otherwise.

If a parcel or right-of-way layer is added later, the class can become
`public`, `private`, or `unknown` with a stated proxy and confidence. A land class is
**not legal title**.

## Privacy rule

Public outputs must be aggregate or candidate-level with no owner information.

Do not track or publish:

- owner names, addresses, or contact details;
- private photos or field notes with identifying details;
- parcel-level ownership claims;
- exact private-tree locations in a public map without a permissioned field protocol.

The demo candidate layer is in `data/demo/ubc_core/off_inventory.json` and is aggregate
screening data. A future private-property pilot needs a written data-sharing and field
access agreement.

## Update workflow

1. Run detection on the latest LiDAR/CHM patch.
2. Match to the current official inventory with a stated tolerance.
3. Classify unmatched crowns by confidence and land class.
4. Write the candidate layer and a review queue.
5. Keep the official and augmented populations separate.
6. Repeat annually or when a new LiDAR acquisition arrives.
7. Promote a candidate to the official inventory only after a permitted field or imagery
   check.

## Licences

- UBC tree inventory: UBC Geodata / UBC Campus as a Living Lab terms.
- UBC 2021 LiDAR: UBC Geodata terms; see the catalog and `DATA_LICENSES.md`.
- City of Vancouver public trees and LiDAR: OGL-Vancouver.
- Parcel layers, if added: check the parcel publisher’s licence before use.

## Reporting rule

Every off-inventory number must name:

- the detection method and parameters;
- the inventory match tolerance;
- the candidate cap and confidence threshold;
- the land-class proxy and its limits;
- the field-validation status.

A candidate is not a tree until it is verified.
