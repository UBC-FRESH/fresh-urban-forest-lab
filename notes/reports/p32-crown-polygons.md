# P32 candidate crown polygons

Date: 2026-11-06

Status: screening crown polygons built for 333,752 of 335,471 candidates.

## What changed

The watershed detector already produced crown segments, but the original candidate table
kept only centroid, area, and equivalent radius. The segment masks are now converted to
simplified exterior polygons and persisted as:

`data/processed/vancouver_2022/off_inventory_crown_polygons.geojson.gz`

- 333,752 polygon features
- 31 MB compressed
- properties: candidate ID, height, confidence, land proxy, support class
- exterior rings simplified by 0.35 grid cells
- same 25 m maximum crown-radius filter as the candidate table

About 1,719 candidates have no polygon: some segments vectorise as a non-Polygon geometry or
do not match a candidate centre within 0.5 m. Their point/radius record remains available.

## Use

- The Vancouver 2D map has a low-opacity orange polygon fill and orange outline layer,
  toggled with the off-inventory layer and filtered by the same confidence/land/support
  controls.
- The human-verification packet now draws the orange watershed outline over each crop.
  The red X remains the candidate centroid; the orange outline is the segment boundary.
- The 3D candidate trees still use ellipsoid crown approximations from height and radius.
  They are not extruded from the polygon footprint yet.

## Limits

- Crown polygons are watershed segments from a 2 m CHM, not field-measured crown
  boundaries.
- A segment can be merged, clipped at a tile edge, or oversized; the 25 m filter removes
  the worst flood segments.
- The polygon layer is for screening and visual audit, not ownership or a census.
