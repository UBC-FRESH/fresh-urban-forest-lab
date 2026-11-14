# P58 street-level first-person navigation

Status: implementation complete; PR review pending.

## Implemented

- **Walk** / **Orbit** toggle in the 3D HUD.
- Pointer-lock mouse look with pitch clamping.
- WASD and arrow-key movement, Shift sprint.
- Terrain-following eye height at 1.7 m.
- Scene-bounds clamping.
- Crosshair and instruction overlay.
- Exiting Walk restores OrbitControls; changing tabs exits Walk mode.

## Verification

Browser smoke on the UBC demo:

- Walk mode entered from the 3D scene.
- Camera moved to terrain eye height.
- `W` changed camera position along the walking direction.
- Orbit restored and the walk HUD hid.
- No page errors.

## Limits

- Not Google Street View imagery.
- No building interiors or complete physical collision.
- Terrain height is the dataset grid, not survey-grade pedestrian ground.
- No jump/crouch or physics.
