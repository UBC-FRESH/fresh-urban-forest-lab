# P61 Walk mode v2

Status: complete. Squash-merged in PR #313 as `dd43436`.

## Implemented

- **Street** spawn: enters Walk mode at the nearest OSM road centreline point and faces
  along the street; falls back to the current target when roads are unavailable.
- Building collision using compact `building_boxes` or full-scene `rings_local`
  footprints, a 2D spatial grid, a small player radius, and axis-slide movement.
- Step-up limit of 0.72 m; ordinary terrain slopes remain walkable.
- Smoothed eye-height following.
- Compass with cardinal heading and bearing.
- Local UTM coordinates and ground elevation.
- Local minimap with nearby roads, building footprints, player marker, and north label.
- Shadow rendering is disabled while walking and restored on exit.
- Existing pointer lock, WASD/arrows, Shift sprint, Escape, and Orbit behavior preserved.

## Verification

### UBC demo

- Street spawn entered Walk mode at the nearest road.
- HUD and minimap visible; compass and coordinates updated.
- `W` moved the camera.
- 734 obstacle grid cells and 9,664 road segments were indexed.
- Spawn point was not blocked; nearby probes included both blocked and open points.
- No page errors.

### Vancouver city scene

- Street spawn entered Walk mode.
- 24,418 obstacle grid cells and 147,193 road segments were indexed.
- HUD, minimap, coordinates, and heading were present.
- No page errors.
- The headless software renderer ran at about 1 frame per second at street level. This is
  a renderer/headless limitation, not a collision or HUD failure; a hardware-GPU frame-rate
  benchmark is still required.

## Limits

- Building footprints block movement, but interiors, stairs, doors, and full physics are
  not modelled.
- Trees are not collision objects.
- Terrain height is still the dataset grid, not survey-grade pedestrian ground.
- This is not Google Street View imagery.

## Close-out

- PR #313 squash-merged into `main` as `dd43436`.
- Public portal restarted on the release code from `main-worktree`.
- `/`, `/ubc/`, `/vancouver/`, `/surrey/`, `/burnaby/`, and `/coquitlam/` returned HTTP 200.
- Deployed UBC smoke passed: Street spawn, HUD, minimap, coordinates, and walking input.
- No product or scientific claims changed.
- Dashboard: **GREEN**.
