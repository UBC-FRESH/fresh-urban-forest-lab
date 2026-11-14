# P58 street-level first-person navigation

Status: complete.

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

## Close-out

- Merged PR #307 into `main` as `c9d67f7`.
- Deployed `main` on the public portal at `:8101` from the `main-worktree` checkout with
  `PYTHONPATH=src`.
- Portal routes `/`, `/ubc/`, `/vancouver/`, `/surrey/`, `/burnaby/`, and
  `/coquitlam/` returned HTTP 200.
- Deployed UBC browser smoke passed: Walk mode entered, pointer lock captured, HUD
  appeared, `W` was accepted, and Orbit restored with the HUD hidden.
- No browser page errors.

## Dashboard

`python scripts/dashboard.py`: **GREEN**. Every gate passed before merge; CI checks
`Green dashboard summary`, `Pre-commit parity`, and `Quality gates` passed on PR #307.
