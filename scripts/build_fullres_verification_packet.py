#!/usr/bin/env python3
# ruff: noqa: E501, RUF001
"""Build a blind, offline P37 human-verification packet for candidate image review."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import shutil
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from PIL import Image, ImageDraw
from rasterio.features import shapes
from rasterio.windows import Window
from scipy import ndimage
from shapely.geometry import shape

from fresh_urban_forest.terrain import project_lonlat, unproject_xy

TEMPLATE_PATH = Path(__file__).with_name("p37_verification_template.html")
SERVER_PATH = Path(__file__).with_name("p37_review_server.py")

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>P37 candidate verification</title>
<style>
:root { --ink:#17231d; --soft:#5f6e64; --line:#d5dfd1; --green:#2f6b4f; --amber:#b8641d; --bg:#f5f7f2; }
* { box-sizing:border-box; }
body { margin:0; font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif; color:var(--ink); background:var(--bg); }
header { position:sticky; top:0; z-index:2; background:#fff; border-bottom:1px solid var(--line); padding:14px 20px; }
h1 { margin:0 0 4px; font-size:1.25rem; }
.wrap { max-width:1500px; margin:0 auto; padding:18px 20px 60px; }
.muted { color:var(--soft); }
.bar { display:flex; flex-wrap:wrap; gap:12px; align-items:center; margin-top:10px; }
.bar input[type=text] { min-width:180px; padding:6px 8px; border:1px solid var(--line); border-radius:6px; }
.bar select, .bar button, .file { padding:6px 9px; border:1px solid var(--line); border-radius:6px; background:#fff; color:var(--ink); font:inherit; }
button { cursor:pointer; }
.progress { height:8px; background:#e6ede3; border-radius:99px; overflow:hidden; flex:1 1 220px; min-width:180px; }
.progress span { display:block; height:100%; width:0; background:var(--green); transition:width .15s; }
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(250px,1fr)); gap:14px; margin-top:18px; }
.card { background:#fff; border:1px solid var(--line); border-radius:10px; padding:9px; }
.card img { width:100%; aspect-ratio:1; object-fit:cover; border-radius:6px; display:block; background:#dfe5dc; }
.card .id { font:12px ui-monospace,SFMono-Regular,Menlo,monospace; margin:7px 0 3px; color:var(--soft); }
.card .meta { font-size:12px; color:var(--soft); min-height:18px; display:none; }
.card.show-meta .meta { display:block; }
.choices { display:flex; gap:5px; margin-top:7px; }
.choices button { flex:1; padding:6px 2px; font-size:12px; }
.choices button.C { border-color:#2f6b4f; }
.choices button.D { border-color:#b4483e; }
.choices button.U { border-color:#9a7b2f; }
.choices button.selected.C { background:#2f6b4f; color:#fff; }
.choices button.selected.D { background:#b4483e; color:#fff; }
.choices button.selected.U { background:#9a7b2f; color:#fff; }
.card textarea { width:100%; min-height:34px; margin-top:6px; resize:vertical; border:1px solid var(--line); border-radius:5px; padding:4px 5px; font:12px/1.3 inherit; }
.card.done { border-color:#7faa75; }
.legend { background:#fff; border:1px solid var(--line); border-radius:10px; padding:12px 16px; margin-top:16px; }
.legend strong { color:var(--green); }
.legend ul { margin:6px 0 0 18px; padding:0; }
.legend li { margin:3px 0; }
.actions { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
.status { font-size:12px; color:var(--soft); }
@media print {
  header, .bar, .legend, .actions, .card textarea { display:none !important; }
  .wrap { max-width:none; padding:0; }
  .grid { grid-template-columns:repeat(4,1fr); gap:8px; }
  .card { break-inside:avoid; border:1px solid #bbb; }
  .card img { max-height:150px; }
}
</style>
</head>
<body>
<header>
  <h1>P37 candidate verification</h1>
  <div class="muted">Blind visual review of 200 orthophoto crops. The crosshair marks the candidate. Do not use the model’s prior labels.</div>
  <div class="bar">
    <label>Reviewer <input id="reviewer" type="text" placeholder="name or initials"></label>
    <div class="progress" aria-label="review progress"><span id="progress"></span></div>
    <span class="status" id="counts">0 / 200 reviewed</span>
    <label class="file">Filter <select id="filter"><option value="all">all</option><option value="unlabeled">unlabeled</option><option value="C">conifer</option><option value="D">deciduous</option><option value="U">uncertain</option></select></label>
    <label><input id="showMeta" type="checkbox"> show model context</label>
    <button id="export">Export labels CSV</button>
    <label class="file">Import <input id="import" type="file" accept=".csv,text/csv"></label>
    <button id="reset">Reset</button>
  </div>
</header>
<div class="wrap">
  <section class="legend">
    <strong>Label definitions</strong>
    <ul>
      <li><b>Conifer:</b> a conifer tree group under the crosshair: needles/scale foliage, conical or layered crown form, or clearly identifiable conifer habit.</li>
      <li><b>Deciduous:</b> a broadleaf/deciduous tree group under the crosshair, including flowering or bare-crown deciduous trees.</li>
      <li><b>Uncertain:</b> the crop is too ambiguous, the crosshair is on an edge, or you cannot tell tree from building/vegetation. Do not guess.</li>
    </ul>
    <p class="muted">The red X is the candidate point, not a claim that a tree is there. If the X falls on the edge of a clearly identifiable tree crown, label <b>Conifer</b> and note “edge”. If it falls outside the crown, label <b>Deciduous</b> or <b>Uncertain</b>. Click the image to open the full crop. Labels save automatically in this browser. Export often. This is a visual pre-audit, not a field measurement.</p>
  </section>
  <div class="grid" id="grid"></div>
</div>
<script>
const CANDIDATES = __CANDIDATES__;
const KEY = "fresh-p37-verification-v1";
let state = JSON.parse(localStorage.getItem(KEY) || '{"labels":{},"notes":{},"reviewer":""}');
const $ = (id) => document.getElementById(id);
function save() { localStorage.setItem(KEY, JSON.stringify(state)); }
function reviewed() { return Object.values(state.labels).filter(Boolean).length; }
function update() {
  const done = reviewed();
  $("progress").style.width = `${(done / CANDIDATES.length) * 100}%`;
  $("counts").textContent = `${done} / ${CANDIDATES.length} reviewed · ` +
    `C ${Object.values(state.labels).filter(v => v === "C").length} · ` +
    `D ${Object.values(state.labels).filter(v => v === "D").length} · ` +
    `U ${Object.values(state.labels).filter(v => v === "U").length}`;
  for (const card of document.querySelectorAll(".card")) {
    const id = card.dataset.id;
    const label = state.labels[id] || "";
    card.classList.toggle("done", Boolean(label));
    for (const button of card.querySelectorAll(".choices button")) {
      button.classList.toggle("selected", button.dataset.value === label);
    }
    const note = card.querySelector("textarea");
    if (note.value !== (state.notes[id] || "")) note.value = state.notes[id] || "";
  }
}
function setLabel(id, value) {
  state.labels[id] = value;
  save(); update();
}
function render() {
  const filter = $("filter").value;
  $("grid").innerHTML = CANDIDATES.filter(c => {
    const label = state.labels[c.id] || "";
    return filter === "all" || (filter === "unlabeled" ? !label : label === filter);
  }).map(c => `
    <article class="card${$("showMeta").checked ? " show-meta" : ""}" data-id="${c.id}">
      <a href="${c.image}" target="_blank" rel="noopener"><img loading="lazy" src="${c.image}" alt="Candidate ${c.id}"></a>
      <div class="id">${c.id}</div>
      <div class="meta">confidence ${c.confidence} · height ${c.height_m} m · crown ${c.crown_diameter_m} m · ${c.land_class}</div>
      <div class="choices">
        <button data-value="C" class="C" type="button">Conifer</button>
        <button data-value="D" class="D" type="button">Deciduous</button>
        <button data-value="U" class="U" type="button">Uncertain</button>
      </div>
      <textarea placeholder="optional note"></textarea>
    </article>`).join("");
  for (const card of document.querySelectorAll(".card")) {
    const id = card.dataset.id;
    for (const button of card.querySelectorAll(".choices button")) {
      button.addEventListener("click", () => setLabel(id, button.dataset.value));
    }
    card.querySelector("textarea").addEventListener("input", (event) => {
      state.notes[id] = event.target.value; save();
    });
  }
  update();
}
function exportCsv() {
  const rows = [["candidate_id", "human_label", "notes"]];
  for (const c of CANDIDATES) rows.push([c.id, state.labels[c.id] || "", state.notes[c.id] || ""]);
  const blob = new Blob([rows.map(row => row.map(v => `"${String(v).replaceAll('"', '""')}"`).join(",")).join("\\n") + "\\n"], {type:"text/csv"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "p37_human_labels.csv";
  a.click();
  URL.revokeObjectURL(a.href);
}
function importCsv(file) {
  const reader = new FileReader();
  reader.onload = () => {
    const lines = String(reader.result).split(/\\r?\\n/).filter(Boolean);
    const header = lines.shift().split(",");
    const idAt = header.indexOf("candidate_id");
    const labelAt = header.indexOf("human_label");
    const noteAt = header.indexOf("notes");
    if (idAt < 0 || labelAt < 0) return;
    for (const line of lines) {
      const cells = line.match(/("([^"]|"")*"|[^,]*)(,|$)/g)?.map(v => v.replace(/,$/, "").replace(/^"|"$/g, "").replaceAll('""', '"')) || [];
      const id = cells[idAt];
      if (!id) continue;
      state.labels[id] = cells[labelAt] || "";
      state.notes[id] = noteAt >= 0 ? cells[noteAt] || "" : "";
    }
    save(); render();
  };
  reader.readAsText(file);
}
$("showMeta").addEventListener("change", render);
$("filter").addEventListener("change", render);
$("export").addEventListener("click", exportCsv);
$("import").addEventListener("change", (event) => { if (event.target.files[0]) importCsv(event.target.files[0]); });
$("reviewer").value = state.reviewer || "";
$("reviewer").addEventListener("input", (event) => { state.reviewer = event.target.value; save(); });
$("reset").addEventListener("click", () => { if (confirm("Clear all labels and notes?")) { state = {labels:{},notes:{},reviewer:""}; save(); $("reviewer").value = ""; render(); } });
render();
</script>
</body>
</html>
"""


def _circle_ring(x: float, y: float, radius_m: float) -> list[list[float]]:
    """Return a WGS84 circle as a last-resort crown footprint.

    Parameters
    ----------
    x, y : float
        Centre in EPSG:3157.
    radius_m : float
        Circle radius in metres.

    Returns
    -------
    list of list of float
        Closed WGS84 ring.
    """
    points: list[list[float]] = []
    for index in range(24):
        angle = index / 24.0 * 2.0 * math.pi
        px = x + math.cos(angle) * radius_m
        py = y + math.sin(angle) * radius_m
        lon, lat = unproject_xy(px, py, "EPSG:3157")
        points.append([lon, lat])
    points.append(points[0])
    return points


def _lcc_ring(
    x: float,
    y: float,
    crown_radius_m: float,
    classes: np.ndarray,
    left: float,
    top: float,
    resolution_m: float,
) -> list[list[float]] | None:
    """Return a local LCC canopy patch ring around a candidate.

    Parameters
    ----------
    x, y : float
        Candidate centre in EPSG:3157.
    crown_radius_m : float
        Candidate crown radius.
    classes : numpy.ndarray
        LCC class grid clipped to the city.
    left, top : float
        Grid upper-left coordinates.
    resolution_m : float
        Grid cell side in metres.

    Returns
    -------
    list of list of float or None
        Closed WGS84 ring, or ``None`` when no tree class is present.
    """
    col = round((x - left) / resolution_m)
    row = round((top - y) / resolution_m)
    half = max(3, math.ceil(max(20.0, crown_radius_m * 3.0) / resolution_m))
    c0 = max(0, col - half)
    c1 = min(classes.shape[1], col + half + 1)
    r0 = max(0, row - half)
    r1 = min(classes.shape[0], row + half + 1)
    if c1 <= c0 or r1 <= r0:
        return None
    window = np.isin(classes[r0:r1, c0:c1], (6, 7, 15, 16)).astype(np.uint8)
    labels, _count = ndimage.label(window, structure=np.ones((3, 3)))
    centre_col = min(max(col - c0, 0), labels.shape[1] - 1)
    centre_row = min(max(row - r0, 0), labels.shape[0] - 1)
    label = int(labels[centre_row, centre_col])
    if label == 0:
        tree_labels = np.unique(labels[window > 0])
        if len(tree_labels) == 0:
            return None
        label = int(tree_labels[0])
    component = labels == label
    transform = rasterio.transform.from_origin(
        left + c0 * resolution_m,
        top - r0 * resolution_m,
        resolution_m,
        resolution_m,
    )
    polygons = [
        shape(geometry)
        for geometry, value in shapes(
            component.astype("uint8"), mask=component, transform=transform
        )
        if int(value) == 1
    ]
    if not polygons:
        return None
    polygon = max(polygons, key=lambda item: item.area).simplify(resolution_m * 0.35)
    ring = []
    for px, py in polygon.exterior.coords:
        lon, lat = unproject_xy(float(px), float(py), "EPSG:3157")
        ring.append([lon, lat])
    return ring if len(ring) >= 4 else None


def _fallback_ring(
    x: float,
    y: float,
    crown_radius_m: float,
    chm_path: Path,
) -> list[list[float]]:
    """Return a local CHM canopy ring, or a radius ring as last resort.

    Parameters
    ----------
    x, y : float
        Candidate centre in EPSG:3157.
    crown_radius_m : float
        Candidate crown radius.
    chm_path : pathlib.Path
        Local CHM raster.

    Returns
    -------
    list of list of float
        Exterior ring in WGS84 coordinate order.
    """
    try:
        with rasterio.open(chm_path) as dataset:
            radius_m = max(20.0, crown_radius_m * 3.0)
            col, row = (~dataset.transform) @ (x, y)
            half = max(4, math.ceil(radius_m / dataset.res[0]))
            window = Window(col - half, row - half, half * 2, half * 2)
            array = dataset.read(1, window=window)
            mask = np.asarray(array >= 2.0, dtype=np.uint8)
            labels, _count = ndimage.label(mask, structure=np.ones((3, 3)))
            centre_col = round(half)
            centre_row = round(half)
            if 0 <= centre_row < labels.shape[0] and 0 <= centre_col < labels.shape[1]:
                label = int(labels[centre_row, centre_col])
            else:
                label = 0
            if label > 0:
                component = labels == label
                transform = dataset.window_transform(window)
                polygons = [
                    shape(geometry)
                    for geometry, value in shapes(
                        component.astype("uint8"), mask=component, transform=transform
                    )
                    if int(value) == 1
                ]
                if polygons:
                    polygon = max(polygons, key=lambda item: item.area).simplify(5.0)
                    ring = list(polygon.exterior.coords)
                    return [
                        [
                            float(unproject_xy(float(px), float(py), "EPSG:3157")[0]),
                            float(unproject_xy(float(px), float(py), "EPSG:3157")[1]),
                        ]
                        for px, py in ring
                    ]
    except Exception:
        pass
    return _circle_ring(x, y, crown_radius_m)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Parameters
    ----------
    argv : list of str or None
        Arguments. ``None`` uses ``sys.argv``.

    Returns
    -------
    argparse.Namespace
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit-csv",
        type=Path,
        default=Path("data/processed/surrey_2025/fullres_audit/audit_key.csv"),
    )
    parser.add_argument(
        "--vrt",
        type=Path,
        default=Path("data/processed/surrey_2025/fullres.vrt"),
    )
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("data/processed/surrey_2025/off_inventory.geojson.gz"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/processed/surrey_2025/fullres_verification_packet"),
    )
    parser.add_argument(
        "--crowns",
        type=Path,
        default=Path("data/processed/surrey_2025/off_inventory_crown_polygons.geojson.gz"),
    )
    parser.add_argument(
        "--chm",
        type=Path,
        default=Path("data/processed/surrey_2025/_chm.tif"),
    )
    parser.add_argument(
        "--lcc",
        type=Path,
        default=Path("data/tmp/lcc_tif/LCC2020/LCC2020.tif"),
    )
    parser.add_argument(
        "--boundary",
        type=Path,
        default=Path("data/processed/surrey_2025/boundary.geojson"),
    )
    parser.add_argument("--size", type=int, default=384)
    parser.add_argument("--no-zip", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Build the blind verification packet and optional ZIP.

    Parameters
    ----------
    argv : list of str or None
        Command-line arguments. ``None`` uses ``sys.argv``.

    Returns
    -------
    int
        Process status.
    """
    from fresh_urban_forest.fullres_imagery import FullResolutionSource

    args = parse_args(argv)
    with args.audit_csv.open(newline="", encoding="utf-8") as handle:
        rows: list[dict[str, str]] = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit("no audit rows")
    with gzip.open(args.features, "rt", encoding="utf-8") as handle:
        collection: dict[str, Any] = json.load(handle)
    features: list[dict[str, Any]] = collection["features"]
    crowns: dict[str, list[list[float]]] = {}
    if args.crowns.exists():
        with gzip.open(args.crowns, "rt", encoding="utf-8") as handle:
            for feature in json.load(handle).get("features", []):
                rings = feature.get("geometry", {}).get("coordinates", [])
                candidate_id = str(feature.get("properties", {}).get("candidate_id", ""))
                if candidate_id and rings:
                    crowns[candidate_id] = rings[0]
    lcc_classes = None
    lcc_left = 0.0
    lcc_top = 0.0
    lcc_res = 5.0
    if args.lcc.exists() and args.boundary.exists():
        try:
            from build_off_inventory_layers import _lcc_grid

            lcc_grid, lcc_classes = _lcc_grid(args.boundary, resolution_m=5.0)
            lcc_left = lcc_grid.left
            lcc_top = lcc_grid.top
            lcc_res = lcc_grid.resolution_m
        except Exception:
            lcc_classes = None
    source = FullResolutionSource(args.vrt, chip_px=args.size)
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    images = out / "images"
    images.mkdir(exist_ok=True)
    candidates: list[dict[str, str]] = []
    template_rows: list[dict[str, str]] = []
    metadata_rows: list[dict[str, str]] = []
    for row in rows:
        index = int(row["candidate_index"])
        candidate_id = row["candidate_id"]
        feature = features[index]
        lon, lat = feature["geometry"]["coordinates"]
        x, y = project_lonlat(float(lon), float(lat), "EPSG:3157")
        chip = source.chip(float(x), float(y), size=args.size)
        image = Image.fromarray(chip, mode="RGB")
        draw = ImageDraw.Draw(image)
        half = args.size // 2
        draw.line((half - 14, half, half + 14, half), fill=(220, 20, 20), width=2)
        draw.line((half, half - 14, half, half + 14), fill=(220, 20, 20), width=2)
        properties = feature.get("properties", {})
        if candidate_id in crowns:
            ring = crowns[candidate_id]
        else:
            radius = float(properties.get("crown_radius_m", 3.0))
            ring = _fallback_ring(float(x), float(y), radius, args.chm)
            if lcc_classes is not None:
                lcc_ring = _lcc_ring(
                    float(x),
                    float(y),
                    radius,
                    lcc_classes,
                    lcc_left,
                    lcc_top,
                    lcc_res,
                )
                if lcc_ring is not None and any(
                    0
                    <= half
                    + (project_lonlat(float(lo), float(la), "EPSG:3157")[0] - float(x))
                    / source.resolution_m
                    <= args.size
                    and 0
                    <= half
                    - (project_lonlat(float(lo), float(la), "EPSG:3157")[1] - float(y))
                    / source.resolution_m
                    <= args.size
                    for lo, la in lcc_ring
                ):
                    ring = lcc_ring
        if ring:
            points = []
            for ring_lon, ring_lat in ring:
                rx, ry = project_lonlat(float(ring_lon), float(ring_lat), "EPSG:3157")
                points.append(
                    (
                        half + (rx - float(x)) / source.resolution_m,
                        half - (ry - float(y)) / source.resolution_m,
                    )
                )
            visible = any(0 <= px <= args.size and 0 <= py <= args.size for px, py in points)
            if len(points) >= 3 and visible:
                draw.line([*points, points[0]], fill=(223, 123, 30), width=3)
            else:
                circle = _circle_ring(
                    float(x),
                    float(y),
                    float(properties.get("crown_radius_m", 3.0)),
                )
                circle_points = [
                    (
                        half
                        + (
                            project_lonlat(float(lon_value), float(lat_value), "EPSG:3157")[0]
                            - float(x)
                        )
                        / source.resolution_m,
                        half
                        - (
                            project_lonlat(float(lon_value), float(lat_value), "EPSG:3157")[1]
                            - float(y)
                        )
                        / source.resolution_m,
                    )
                    for lon_value, lat_value in circle
                ]
                draw.line(
                    [*circle_points, circle_points[0]],
                    fill=(223, 123, 30),
                    width=3,
                )
        name = f"{index:06d}.png"
        image.save(images / name)
        candidates.append(
            {
                "id": candidate_id,
                "image": f"images/{name}",
                "confidence": "",
                "height_m": properties.get("height_m", ""),
                "crown_diameter_m": str(round(float(properties.get("crown_radius_m", 0)) * 2, 1)),
                "land_class": properties.get("land_class", ""),
            }
        )
        template_rows.append(
            {
                "candidate_id": candidate_id,
                "human_label": "",
                "common_comments": "",
                "notes": "",
            }
        )
        metadata_rows.append(
            {
                "candidate_index": row["candidate_index"],
                "candidate_id": candidate_id,
                "page": row.get("page", ""),
                "p_fullres": row.get("p_fullres", ""),
                "p_030": row.get("p_030", ""),
            }
        )
    source.close()
    html = TEMPLATE_PATH.read_text(encoding="utf-8").replace(
        "__CANDIDATES__", json.dumps(candidates, ensure_ascii=False)
    )
    (out / "index.html").write_text(html, encoding="utf-8")
    with (out / "review_template.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["candidate_id", "human_label", "common_comments", "notes"],
        )
        writer.writeheader()
        writer.writerows(template_rows)
    shutil.copy2(SERVER_PATH, out / "review_server.py")
    with (out / "candidate_metadata.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(metadata_rows[0]))
        writer.writeheader()
        writer.writerows(metadata_rows)
    (out / "README.md").write_text(
        "# P37 human verification packet\n\n"
        "Open `index.html` in a browser. Review the 200 centre-cropped 0.075 m orthophoto images.\n\n"
        "- The red crosshair marks the candidate point.\n"
        "- Label each crop Conifer, Deciduous, or Uncertain using the definitions on the page.\n"
        "- Labels save in browser local storage. Export `p37_human_labels.csv` when finished.\n"
        "- Do not open `candidate_metadata.csv` until after the first pass; it contains model probabilities.\n"
        "- Run `python review_server.py` from this directory and open the printed URL for server-backed review; otherwise open `index.html` locally.\n"
        "- This is a blind visual audit, not a field measurement or ownership record.\n\n"
        "Source imagery: City of Surrey Aerial Photo April 2025, 0.075 m SID, decoded locally.\n"
        "The packet contains candidate IDs and crop images only; no owner or address data.\n",
        encoding="utf-8",
    )
    if not args.no_zip:
        archive = out.with_suffix(".zip")
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
            for path in sorted(out.rglob("*")):
                if path.is_file():
                    handle.write(path, path.relative_to(out.parent))
    print(f"packet: {out}")
    print(f"images: {len(candidates)}")
    if not args.no_zip:
        print(f"zip: {out.with_suffix('.zip')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
