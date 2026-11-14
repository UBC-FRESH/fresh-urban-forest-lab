# P58 street-level first-person navigation

Parent issue: #306
Branch: `feature/p58-walk-mode`
Status: complete

## Goal

Add a street-level Walk mode to the existing Three.js scene: pointer-lock mouse look,
WASD/arrow movement, Shift sprint, terrain following, and a clear Orbit/Walk toggle.

This is not Google Street View imagery and does not use Google APIs.

## Scope

- Walk/Orbit button in the 3D HUD.
- Pointer lock on canvas; mouse-look yaw/pitch with clamping.
- WASD and arrow-key movement, Shift sprint.
- Terrain-height eye follow and scene-bounds clamping.
- Preserve OrbitControls and tree selection when not walking.
- Crosshair/instruction overlay.
- Exit Walk when switching tabs or choosing Orbit. Escape releases the pointer lock but
  keeps Walk mode active, with a click-to-look hint.

## Out of scope

- Google Street View panoramas or API keys.
- Building interiors, jump/crouch, physics, or exhaustive collision.
- Map-view navigation.
