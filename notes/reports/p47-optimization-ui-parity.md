# P47 optimization UI parity

Status: complete. Merged in PR #245 as `2b24607`.

## Purpose

Port the high-value Optimization-page interaction patterns developed in
`fable-pyculator` into the FRESH 3D Pareto explorer, adapted to the FRESH archive
semantics. This is a viewer and inspection phase, not a new optimizer.

## Delivered

### P47.1 Viewer state and inspection

- Hover tooltip with solution id and objective values.
- Selected and reference marker meshes.
- Reference objective-delta cards.
- Actual X/Y/Z ideal–nadir ranges.
- Robustness floor, explicitly labelled as a bootstrap diagnostic.
- URL state for axes, colour, size, floor, archive job, selected point, reference,
  brushes, and preset name.
- Copy-view link and filtered CSV export.
- Static web-asset checks.

### P47.2 Parallel coordinates and brushes

- Synchronized SVG parallel-coordinates panel.
- Axes from objectives plus robustness, planted-site count, and habitat; cost/water
  metric fallback only when not already objectives.
- Click a line to select the same solution as the 3D view.
- Selected and reference line emphasis.
- Single-axis brushes and Shift-drag multi-axis brushes with removable chips.
- Brushes combine with AND and filter the 3D cloud, parallel lines, and CSV.
- `opt_brushes` URL round-trip.

### P47.3 Local saved views and preset links

- Named local views in browser storage with save/load/delete.
- Viewer state covers axes, colour, size, robustness floor, brushes, selection,
  reference, and archive/job id.
- Versioned JSON export/import with validation, bounded libraries, and merge-by-name.
- Archive-mismatch refusal instead of silently applying a view to another front.
- `opt_preset` portable links carrying the full viewer state and preset name.

### P47.4 Shared review library

Deferred. It is an optional collaboration layer and is not required for the defensible
single-user explorer. No server-backed shared views, accounts, permissions, verified
review, audit, or timeline are included.

## Evidence

- Dashboard: GREEN (`lint`, `format`, `types`, `tests`, `validator`, `docs`).
- Browser smoke: archive load; hover; selected/reference markers; URL reload with floor,
  point, reference, brushes, and preset; parallel-line selection; Shift-drag brushes;
  filtered CSV; local view save/load/delete; JSON export/import; malformed import
  rejection; archive-mismatch refusal. Final run: 10 axes, 71 initial lines, two brushes
  reduced the view to 4 of 71, the CSV contained exactly 4 rows, and the preset URL
  restored the preset name, floor 40, both brushes, selection, and reference with no page
  errors.
- No new optimizer math or archive claims. Existing archive tests remain the numeric
  oracle.

## Source attribution

Patterns were adapted from the MIT-licensed `fable-pyculator` Optimization work,
principally its phases 41–50: hover/ranges, URL/copy/CSV, parallel coordinates,
reference deltas, brushes, local presets, export/import, and preset deep links.
FABLE-specific quality-floor, warning, dominated-point, and Workbench semantics were
not copied.

## Limits

- The archive is a finite weighted-scalarisation approximation, not a complete front.
- Robustness is a bootstrap diagnostic, not a dominance or feasibility proof.
- Parallel brushes are viewer filters, not planting constraints.
- Local views are browser-local and archive-specific.
- Preset links require the saved archive to exist on the serving deployment.
- No ownership, field validation, survival, or causal claim is added.
