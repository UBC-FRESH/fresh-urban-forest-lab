# P61 Walk mode v2

Parent issue: #312
Branch: `feature/p61-walk-v2`
Status: pr-open

## Goal

Make the existing 3D Walk mode street-navigable: prevent walking through buildings, permit
street spawning, handle ordinary slopes and small steps, and add a compact navigation HUD.

## Design

### Collision

Build a local obstacle index when Walk starts:

- compact scenes use `building_boxes`;
- full scenes use `buildings[].rings_local`;
- a 2D spatial grid keyed by local metres limits checks to nearby cells;
- point-in-polygon blocks building footprints with a small player radius;
- full movement is attempted first, then x-only and z-only sliding.

### Street spawn

The **Street** action converts the current orbit target to the nearest OSM road centreline
point, enters Walk mode there, and looks along the nearest road segment. If roads are not
available, it falls back to the current target with a status message.

### Terrain and steps

Walk keeps the existing terrain-grid eye height, smooths small height changes, and blocks
step-ups above a fixed threshold. Ordinary slopes remain walkable.

### HUD

- compass heading and cardinal label;
- local UTM coordinates and ground elevation;
- small canvas minimap showing nearby roads, building footprints, and the player;
- existing pointer lock, WASD, sprint, Escape, and Orbit behavior preserved.

## Out of scope

- Google Street View imagery or API.
- Jumping, crouching, interiors, stairs, vehicles, and full physics.
- Tree-by-tree collision.
- Changes to the 2D map or scientific products.

## Tasks

- P61.1 Collision, street spawn, slope/step handling.
- P61.2 Compass/coordinates HUD and minimap.
- P61.3 Browser smoke, city-scale performance check, docs, PR, and close-out.
