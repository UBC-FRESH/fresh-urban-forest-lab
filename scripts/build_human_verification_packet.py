#!/usr/bin/env python3
# ruff: noqa: E501, RUF001
"""Build a blind, offline human-verification packet for the candidate audit."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import shutil
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>P32 candidate verification</title>
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
.choices button.T { border-color:#2f6b4f; }
.choices button.N { border-color:#b4483e; }
.choices button.U { border-color:#9a7b2f; }
.choices button.selected.T { background:#2f6b4f; color:#fff; }
.choices button.selected.N { background:#b4483e; color:#fff; }
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
  <h1>P32 candidate verification</h1>
  <div class="muted">Blind visual review of 300 orthophoto crops. The crosshair marks the candidate. Do not use the model’s prior labels.</div>
  <div class="bar">
    <label>Reviewer <input id="reviewer" type="text" placeholder="name or initials"></label>
    <div class="progress" aria-label="review progress"><span id="progress"></span></div>
    <span class="status" id="counts">0 / 300 reviewed</span>
    <label class="file">Filter <select id="filter"><option value="all">all</option><option value="unlabeled">unlabeled</option><option value="T">tree</option><option value="N">non-tree</option><option value="U">uncertain</option></select></label>
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
      <li><b>Tree:</b> a distinct woody tree crown under the crosshair, including an unlisted/private tree. Small ornamental trees count if the crown is distinguishable.</li>
      <li><b>Non-tree:</b> roof, road, sidewalk, lawn, bare soil, water, car, or a hedge/shrub mass that is not a distinguishable tree.</li>
      <li><b>Uncertain:</b> the crop is too ambiguous, the crosshair is on an edge, or you cannot tell tree from building/vegetation. Do not guess.</li>
    </ul>
    <p class="muted">The red X is the candidate point, not a claim that a tree is there. If the X falls on the edge of a clearly identifiable tree crown, label <b>Tree</b> and note “edge”. If it falls outside the crown, label <b>Non-tree</b> or <b>Uncertain</b>. Click the image to open the full crop. Labels save automatically in this browser. Export often. This is a visual pre-audit, not a field measurement.</p>
  </section>
  <div class="grid" id="grid"></div>
</div>
<script>
const CANDIDATES = __CANDIDATES__;
const KEY = "fresh-p32-verification-v1";
let state = JSON.parse(localStorage.getItem(KEY) || '{"labels":{},"notes":{},"reviewer":""}');
const $ = (id) => document.getElementById(id);
function save() { localStorage.setItem(KEY, JSON.stringify(state)); }
function reviewed() { return Object.values(state.labels).filter(Boolean).length; }
function update() {
  const done = reviewed();
  $("progress").style.width = `${(done / CANDIDATES.length) * 100}%`;
  $("counts").textContent = `${done} / ${CANDIDATES.length} reviewed · ` +
    `T ${Object.values(state.labels).filter(v => v === "T").length} · ` +
    `N ${Object.values(state.labels).filter(v => v === "N").length} · ` +
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
        <button data-value="T" class="T" type="button">Tree</button>
        <button data-value="N" class="N" type="button">Non-tree</button>
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
  a.download = "p32_human_labels.csv";
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
        "--labels",
        type=Path,
        default=Path("data/processed/vancouver_2022/off_inventory_audit_labels.csv"),
    )
    parser.add_argument(
        "--crops",
        type=Path,
        default=Path("data/processed/vancouver_2022/off_inventory_audit_sheet/crops"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/processed/vancouver_2022/human_verification_packet"),
    )
    parser.add_argument(
        "--crowns",
        type=Path,
        default=Path("data/processed/vancouver_2022/off_inventory_crown_polygons.geojson.gz"),
    )
    parser.add_argument("--no-zip", action="store_true")
    return parser.parse_args(argv)


def _num(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return 0.0


def main(argv: list[str] | None = None) -> int:
    """Build the packet directory and optional ZIP.

    Parameters
    ----------
    argv : list of str or None
        Command-line arguments. ``None`` uses ``sys.argv``.

    Returns
    -------
    int
        Process status.
    """
    args = parse_args(argv)
    with args.labels.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit("no audit rows")
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    images = out / "images"
    images.mkdir(exist_ok=True)
    crowns: dict[str, list[list[float]]] = {}
    if args.crowns.exists():
        with gzip.open(args.crowns, "rt", encoding="utf-8") as handle:
            for feature in json.load(handle)["features"]:
                rings = feature.get("geometry", {}).get("coordinates", [])
                properties = feature.get("properties", {})
                if rings and properties.get("candidate_id"):
                    crowns[str(properties["candidate_id"])] = rings[0]
    candidates = []
    template_rows = []
    metadata_rows = []
    for row in rows:
        candidate_id = row["candidate_id"]
        source = args.crops / f"{candidate_id}.png"
        if not source.exists():
            raise SystemExit(f"missing crop: {source}")
        destination = images / source.name
        shutil.copy2(source, destination)
        if candidate_id in crowns:
            zoom = 19
            count = 2**zoom
            center_lon = float(row["lon"])
            center_lat = float(row["lat"])
            center_x = (center_lon + 180.0) / 360.0 * count * 512
            center_y = (
                (1.0 - math.asinh(math.tan(math.radians(center_lat))) / math.pi) / 2.0 * count * 512
            )
            image = Image.open(destination).convert("RGB")
            draw = ImageDraw.Draw(image)
            points = []
            for lon, lat in crowns[candidate_id]:
                px = (float(lon) + 180.0) / 360.0 * count * 512 - center_x + 160
                py = (
                    (1.0 - math.asinh(math.tan(math.radians(float(lat)))) / math.pi)
                    / 2.0
                    * count
                    * 512
                    - center_y
                    + 160
                )
                points.append((px, py))
            if len(points) >= 3:
                draw.line([*points, points[0]], fill="#df7b1e", width=2)
            image.save(destination)
        candidates.append(
            {
                "id": candidate_id,
                "image": f"images/{source.name}",
                "confidence": row.get("confidence", ""),
                "height_m": row.get("height_m", ""),
                "crown_diameter_m": round(_num(row.get("crown_radius_m", "0")) * 2, 1),
                "land_class": row.get("land_class", "unknown"),
            }
        )
        template_rows.append({"candidate_id": candidate_id, "human_label": "", "notes": ""})
        metadata_rows.append(
            {
                "candidate_id": candidate_id,
                "ai_label": row.get("audit_label", ""),
                "confidence": row.get("confidence", ""),
                "land_class": row.get("land_class", ""),
                "height_m": row.get("height_m", ""),
                "crown_radius_m": row.get("crown_radius_m", ""),
                "local_area": row.get("local_area", ""),
            }
        )
    html = TEMPLATE.replace("__CANDIDATES__", json.dumps(candidates, ensure_ascii=False))
    (out / "index.html").write_text(html, encoding="utf-8")
    with (out / "review_template.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["candidate_id", "human_label", "notes"])
        writer.writeheader()
        writer.writerows(template_rows)
    with (out / "candidate_metadata.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(metadata_rows[0]))
        writer.writeheader()
        writer.writerows(metadata_rows)
    (out / "README.md").write_text(
        "# P32 human verification packet\n\n"
        "Open `index.html` in a browser. Review the 300 centre-cropped orthophoto images.\n\n"
        "- The red X is the candidate point. The orange outline, when present, is the watershed crown segment.\n"
        "- A point on the edge of a clearly identifiable crown is still Tree; note it as edge. A point just outside the crown is Non-tree or Uncertain.\n"
        "- Label each crop Tree, Non-tree, or Uncertain using the definitions on the page.\n"
        "- Labels save in browser local storage. Export `p32_human_labels.csv` when finished.\n"
        "- Do not open `candidate_metadata.csv` until after the first pass; it contains the prior AI labels.\n"
        "- This is a blind visual audit, not a field measurement or ownership record.\n\n"
        "Source imagery: Data For Canada PMTiles mirror of the City of Vancouver 2022 7.5 cm orthophoto.\n"
        "The packet contains candidate coordinates and crop images only; no owner or address data.\n",
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
