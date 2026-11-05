# ruff: noqa: E501
"""A small landing portal that mounts the UBC and Vancouver demo apps.

The portal is a runtime convenience, not a second model layer. Each mounted app keeps its
own dataset, scenarios, and runtime directory; the landing page only reads their manifests
and city-metrics file to render status cards.
"""

from __future__ import annotations

import html
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from fresh_urban_forest.dataset import load_dataset
from fresh_urban_forest.service import create_app


@dataclass(frozen=True, slots=True)
class PortalDemo:
    """One demo application mounted under the portal.

    Attributes
    ----------
    slug : str
        URL segment, such as ``ubc`` or ``vancouver``.
    label : str
        Short card title.
    subtitle : str
        One-line description.
    dataset_root : Path
        Dataset directory.
    runtime_dir : Path
        Scenario directory for this app instance.
    description : str
        Longer card text.
    image : str
        Optional image filename under the portal assets directory.
    """

    slug: str
    label: str
    subtitle: str
    dataset_root: Path
    runtime_dir: Path
    description: str
    image: str = ""


@dataclass(frozen=True, slots=True)
class DemoCard:
    """Read-only status for one mounted demo."""

    slug: str
    label: str
    subtitle: str
    description: str
    image: str
    tree_count: int
    canopy_cover_pct: float
    canopy_volume_m3: float
    carbon_kg: float
    extra: Mapping[str, object]


def create_portal_app(
    demos: tuple[PortalDemo, ...],
    *,
    title: str = "FRESH Urban Forest Lab",
    assets_dir: Path | None = None,
    allow_agent: bool = False,
) -> FastAPI:
    """Create the landing portal and mount each demo app.

    Parameters
    ----------
    demos : tuple of PortalDemo
        Demos to mount.
    title : str
        Portal title.
    assets_dir : Path or None
        Optional static image directory.
    allow_agent : bool
        Enable the local assistant in each mounted app.

    Returns
    -------
    FastAPI
        Portal application.
    """
    app = FastAPI(title=title)
    cards: list[DemoCard] = []
    for demo in demos:
        dataset = load_dataset(demo.dataset_root)
        demo.runtime_dir.mkdir(parents=True, exist_ok=True)
        mounted = create_app(
            dataset,
            runtime_dir=demo.runtime_dir,
            dataset_root=demo.dataset_root,
            allow_agent=allow_agent,
        )
        app.mount(f"/{demo.slug}", mounted)
        metrics = dataset.manifest.metrics
        city_metrics = _city_metrics(demo.dataset_root)
        cards.append(
            DemoCard(
                slug=demo.slug,
                label=demo.label,
                subtitle=demo.subtitle,
                description=demo.description,
                image=demo.image,
                tree_count=metrics.tree_count,
                canopy_cover_pct=metrics.canopy_cover_pct,
                canopy_volume_m3=metrics.canopy_volume_m3,
                carbon_kg=metrics.total_carbon_kg,
                extra=city_metrics,
            )
        )
    if assets_dir is not None and assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/", response_class=HTMLResponse)
    def landing(request: Request) -> HTMLResponse:
        """Render the demo chooser.

        Parameters
        ----------
        request : Request
            Incoming request.

        Returns
        -------
        HTMLResponse
            Landing page.
        """
        return HTMLResponse(
            _landing(title, cards),
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    @app.get("/api/demos")
    def demo_status() -> JSONResponse:
        """Return the mounted demo cards as JSON.

        Returns
        -------
        JSONResponse
            Demo status payload.
        """
        return JSONResponse(
            {
                "title": title,
                "demos": [
                    {
                        "slug": card.slug,
                        "label": card.label,
                        "subtitle": card.subtitle,
                        "tree_count": card.tree_count,
                        "canopy_cover_pct": card.canopy_cover_pct,
                        "canopy_volume_m3": card.canopy_volume_m3,
                        "carbon_kg": card.carbon_kg,
                    }
                    for card in cards
                ],
            },
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    @app.get("/health")
    def health() -> dict[str, object]:
        """Return portal readiness.

        Returns
        -------
        dict
            Portal health and mounted demo slugs.
        """
        return {"status": "ok", "demos": [card.slug for card in cards]}

    return app


def _city_metrics(root: Path) -> Mapping[str, object]:
    """Read optional city metrics for a demo card.

    Parameters
    ----------
    root : Path
        Dataset directory.

    Returns
    -------
    mapping
        City metrics payload, or an empty mapping.
    """
    path = root / "city_metrics.json"
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    return cast(Mapping[str, object], payload)


def _landing(title: str, cards: list[DemoCard]) -> str:
    """Build the landing page HTML.

    Parameters
    ----------
    title : str
        Portal title.
    cards : list of DemoCard
        Demo cards.

    Returns
    -------
    str
        HTML document.
    """
    card_html = []
    for card in cards:
        image = (
            f'<img class="card-image" src="assets/{html.escape(card.image)}" alt="" loading="lazy">'
            if card.image
            else ""
        )
        volume = card.canopy_volume_m3 / 1_000_000.0
        carbon = card.carbon_kg / 1_000.0
        city = card.extra.get("city") if card.extra else None
        city_note = ""
        if isinstance(city, dict):
            sequestration = float(city.get("annual_sequestration_kg", 0.0)) / 1_000.0
            city_note = f"<span>{sequestration:,.0f} t/yr sequestration</span>"
        card_html.append(
            f"""<a class="door" href="./{html.escape(card.slug)}/">
  {image}
  <div class="card-body">
    <div class="card-top"><span class="kicker">{html.escape(card.subtitle)}</span><span class="badge">LIVE</span></div>
    <h2>{html.escape(card.label)}</h2>
    <p>{html.escape(card.description)}</p>
    <div class="stats">
      <span><strong>{card.tree_count:,}</strong> trees</span>
      <span><strong>{card.canopy_cover_pct:.1f}%</strong> canopy cover</span>
      <span><strong>{volume:,.1f}M m³</strong> canopy volume</span>
      <span><strong>{carbon:,.0f} t</strong> carbon</span>
      {city_note}
    </div>
    <div class="arrow">Open demo →</div>
  </div>
</a>"""
        )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · demos</title>
<style>
  :root {{ color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, sans-serif; --ink: #17231d; --soft: #5a6b60; --green: #1f6b43; --line: #cddccf; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; min-height: 100vh; color: var(--ink); background: radial-gradient(circle at 10% 0%, #dcecd9, #f7faf3 42%, #e8f0e4 100%); }}
  main {{ width: min(1080px, calc(100vw - 36px)); margin: 0 auto; padding: 54px 0 40px; }}
  .kicker {{ color: var(--green); text-transform: uppercase; letter-spacing: .13em; font-size: .7rem; font-weight: 750; }}
  h1 {{ margin: 8px 0 10px; font-size: clamp(2.4rem, 6vw, 5rem); letter-spacing: -.055em; line-height: .95; }}
  .lead {{ max-width: 760px; margin: 0 0 30px; color: var(--soft); font-size: 1.05rem; line-height: 1.6; }}
  .doors {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }}
  .door {{ display: flex; flex-direction: column; overflow: hidden; border: 1px solid var(--line); border-radius: 18px; background: rgba(255,255,255,.82); box-shadow: 0 18px 50px #173d2a18; text-decoration: none; color: inherit; transition: transform .16s ease, box-shadow .16s ease; }}
  .door:hover {{ transform: translateY(-4px); box-shadow: 0 24px 60px #173d2a24; }}
  .card-image {{ width: 100%; height: 210px; object-fit: cover; object-position: top; display: block; background: #dfe9da; }}
  .card-body {{ padding: 18px 20px 22px; display: flex; flex-direction: column; flex: 1; }}
  .card-top {{ display: flex; justify-content: space-between; align-items: center; gap: 10px; }}
  .badge {{ font-size: .62rem; font-weight: 800; letter-spacing: .1em; color: var(--green); background: #e2f2e5; border: 1px solid #b8ddc0; border-radius: 999px; padding: 5px 8px; }}
  h2 {{ margin: 12px 0 7px; font-size: 1.55rem; letter-spacing: -.03em; }}
  .door p {{ margin: 0; color: var(--soft); line-height: 1.48; font-size: .92rem; }}
  .stats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 7px 12px; margin: 15px 0 0; color: var(--soft); font-size: .75rem; }}
  .stats strong {{ color: var(--ink); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .82rem; }}
  .arrow {{ margin-top: auto; padding-top: 18px; color: var(--green); font-weight: 750; }}
  footer {{ margin-top: 24px; color: var(--soft); font-size: .76rem; line-height: 1.5; }}
  @media (max-width: 760px) {{ .doors {{ grid-template-columns: 1fr; }} main {{ padding-top: 32px; }} .card-image {{ height: 190px; }} }}
</style>
</head>
<body>
<main>
  <div class="kicker">FRESH Urban Forest Lab · public demos</div>
  <h1>Two canopy demos.<br>One lab.</h1>
  <p class="lead">Start with the UBC campus proof, then open the full City of Vancouver pilot. Both demos run the same 2D map, 3D scene, scenario tools, metrics, and evidence labels; the city version adds 181 LiDAR tiles, 184k public trees, and local-area ecosystem-service metrics.</p>
  <div class="doors">{"".join(card_html)}</div>
  <footer>Public data only · City of Vancouver OGL-Vancouver · UBC PDDL-1.0 · LiDAR 2021/2022 · no private data · no accounts</footer>
</main>
</body>
</html>"""
