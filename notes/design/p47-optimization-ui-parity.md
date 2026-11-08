# P47 Optimization UI parity with fable-pyculator patterns

Parent issue: #237
Planned branch: `feature/p47-optimization-ui-parity`
Status: planned

## Why

FRESH originally introduced the 3D Pareto solution-space view. The design pattern was then
carried into `ws4` and `fable-pyculator`, where the Optimization page gained a series of
interaction and review breakthroughs. This phase ports the parts that fit FRESH's archive
model and leaves FABLE-specific semantics behind.

The port is an adaptation, not a copy. Both repositories are MIT; the source phases and
commits will be cited in the report.

## Source pattern inventory

From `fable-pyculator` Phases 41–61:

| Source phase | Pattern | FRESH fit |
| --- | --- | --- |
| 41 | 3D cloud, axis/colour/size mapping, pins, compare, Workbench prefill | Mostly present; keep and extend |
| 42 | Hover values, selected highlight, real axis ranges, legends, warning filter | Port hover, ranges, legend; replace warning filter with robustness floor |
| 43 | URL state, copy link, filtered CSV | Port directly |
| 44 | Synchronized parallel coordinates | Port with fresh objective/metric axes |
| 45 | Reference point and deltas | Port directly |
| 46–47 | Single and multi-axis brushes | Port directly |
| 48–50 | Local saved views, import/export, preset links | Port directly |
| 51–61 | Shared presets, author/note/review, history, audit, timeline, workload | Optional second slice; only after local views are stable |

## Fresh data contract

The browser receives an archive from `/api/optimize/{job_id}`:

- `archive.objectives[]`: `name`, `label`, `direction`
- `archive.ideal[]`, `archive.nadir[]`
- `solutions[]`: `solution_id`, `objectives[]`, `metrics{}`, `planted[]`,
  `robustness`, `constraint_violation`
- `job_id`: used as the viewer/version key

There are no FABLE scenario controls, `warning` flags, dominated points, or quality
scales. The port must therefore:

- show **robustness floor**, not a quality floor;
- use **continuous objective legends**, not categorical control legends;
- derive parallel axes from objectives plus solution metrics (`cost_cad`, `water_l`,
  `native_fraction`, `carbon_kg`, `habitat_index`, planted count, robustness);
- make clear that the archive is already non-dominated, so a "front only" toggle is not
  ported unless a future archive includes dominated candidates.

## P47.1 Viewer state and inspection

- Add hover raycast tooltip with objective values and solution id.
- Add selected and reference marker meshes, not only colour changes.
- Add actual X/Y/Z ranges and direction from `ideal`/`nadir`.
- Add robustness floor control and filtered count.
- Add URL state: `opt_x`, `opt_y`, `opt_z`, `opt_colour`, `opt_size`,
  `opt_floor`, `opt_point`, `opt_reference`, `opt_preset`.
- Add copy-view-link and filtered CSV download.
- Keep pins/compare and the existing "load as scenario" action.

Acceptance: reloading a copied URL restores axes, floor, point, reference, and preset;
CSV contains only visible solutions; keyboard focus and labels remain usable.

## P47.2 Parallel coordinates

- Render a synchronized SVG parallel view for the filtered archive.
- Axes: objectives + selected metrics + robustness/constraint.
- Click a line to select the 3D point; selected/reference lines are emphasized.
- Drag an axis to filter; Shift-drag adds a second brush.
- Show removable brush chips, clear-all, and a visible brush band.
- Round-trip brushes through `opt_brushes` (legacy `opt_brush` accepted).

Acceptance: 3D and parallel selections stay synchronized; brushes combine with AND;
URL state restores multiple brushes; empty states are explicit.

## P47.3 Local saved views

- Save/load/delete named views in `localStorage`.
- State covers axes, colour, size, robustness floor, brushes, reference, selection.
- Export/import a versioned JSON library with validation and merge-by-name.
- Copy a preset link carrying the name plus full viewer state.

Acceptance: import rejects malformed states; presets are bounded; old presets do not
silently apply to a different archive.

## P47.4 Shared review library (optional second slice)

Only after P47.1–P47.3 are green:

- Server-backed named views under the runtime directory.
- List/save/delete APIs with validation and atomic writes.
- Self-declared author, note, draft/reviewed status.
- Compact history, audit JSON/CSV, review timeline, author workload.
- Shared timeline filter views.

This is the collaboration layer, not a prerequisite for the local viewer.

## Testing plan

- Playwright: hover tooltip, selection, reference, URL round-trip, CSV download,
  brush drag/Shift-drag, clear, preset save/load/delete, import/export.
- Service tests: preset validation, atomic writes, 404s, malformed payloads.
- Unit/browser tests for parallel-coordinate normalization and empty states.
- No new optimizer math; existing archive tests remain the numeric oracle.
- Dashboard green on every commit.

## Risks

- **Archive size**: fresh archives can be larger than FABLE's 160 exact points. Cap the
  parallel lines or use line decimation while preserving selected/reference.
- **Semantics**: robustness is not a feasibility warning; labels must say so.
- **State drift**: job ids and archive versions must be part of preset state.
- **Scope creep**: shared review library is optional and must not block the core viewer.

## P48 queued next: site-level planting scenarios

After P47, build a site-level scenario layer rather than more viewer polish:

- derive candidate planting sites from P39 gap components and P42 action cells;
- simulate 3D shade gain with the existing shadow model;
- carry species, cost, water, and maintenance assumptions explicitly;
- compare scenarios in the same 3D/Pareto language where meaningful;
- preserve P45's warning that citywide change direction is unresolved;
- do not call the result a planting plan or field-validated recommendation.

P48 should consume P47's saved-view and parallel-coordinate patterns rather than fork
another explorer.
