"""FastAPI service for the urban-forest decision-support prototype.

The service is deliberately a thin layer over the typed core. It exposes the dataset,
the scene payload, scenarios, a planting recommender, and two image endpoints for the
2D map. Scenario writes are atomic and versioned; a scenario is projected on demand and
cached in memory.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import math
import os
import shutil
import subprocess
import threading
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import numpy as np
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, Field

from fresh_urban_forest.completeness import inventory_completeness
from fresh_urban_forest.dataset import dataset_summary
from fresh_urban_forest.dss import (
    candidates_to_edits,
    compare_scenarios,
    export_scenario_csv,
    export_scenario_geojson,
    metric_delta,
    recommend_planting,
)
from fresh_urban_forest.growth import project_scenario, project_trees_to_year, scenario_summary
from fresh_urban_forest.irrigation import compare_irrigation
from fresh_urban_forest.metrics import compare_metrics
from fresh_urban_forest.models import (
    CanopyMetrics,
    Scenario,
    ScenarioEdit,
    ScenarioResult,
    TreeRecord,
    UrbanForestDataset,
    edit_to_dict,
    scenario_from_dict,
    scenario_to_dict,
)
from fresh_urban_forest.scene import build_scene
from fresh_urban_forest.shade import (
    ShadePeriod,
    default_step_hours,
    shade_at_tree,
    shade_period,
    shade_png,
)
from fresh_urban_forest.solar import (
    DEFAULT_TIMES,
    DEFAULT_TIMEZONE,
    parse_clock,
    parse_date,
    representative_time_grid,
    solar_position,
    time_grid,
)
from fresh_urban_forest.species import (
    all_profiles,
    profile_for_species,
    site_fit,
)
from fresh_urban_forest.terrain import unproject_xy
from fresh_urban_forest.vigor import growth_response, project_species_growth
from fresh_urban_forest.water import (
    compare_water_policies,
    simulate_water_balance,
)

DEFAULT_AGENT_MODEL = "opencode-go/deepseek-v4.1-flash"
OPTIMIZATION_DIR = "optimizations"


class EditInput(BaseModel):
    """One edit submitted by the browser."""

    kind: Literal["plant", "remove", "replace", "move"] = "plant"
    tree_id: str
    lon: float | None = None
    lat: float | None = None
    species: str | None = None
    common_name: str | None = None
    dbh_cm: float | None = Field(default=None, ge=0.1, le=300.0)
    height_m: float | None = Field(default=None, ge=0.2, le=120.0)
    crown_width_m: float | None = Field(default=None, ge=0.1, le=60.0)
    note: str = ""


class ScenarioInput(BaseModel):
    """A scenario creation request."""

    name: str = Field(default="New scenario", min_length=1, max_length=120)
    years: int = Field(default=25, ge=0, le=100)
    edits: list[EditInput] = Field(default_factory=list)


class ScenarioPatch(BaseModel):
    """An append request for an existing scenario."""

    edits: list[EditInput] = Field(default_factory=list)
    revision: int | None = None


class PlantingRequest(BaseModel):
    """A planting recommendation request."""

    count: int = Field(default=50, ge=1, le=2000)
    species: str = Field(default="Acer macrophyllum", min_length=1, max_length=120)
    common_name: str = ""
    budget_cad: float | None = Field(default=None, ge=0.0)
    grid_m: float = Field(default=8.0, ge=2.0, le=50.0)
    center_lon: float | None = Field(default=None, ge=-180.0, le=180.0)
    center_lat: float | None = Field(default=None, ge=-90.0, le=90.0)
    radius_m: float | None = Field(default=None, ge=5.0, le=5000.0)


class ScenarioStore(BaseModel):
    """A list of scenario summaries."""

    scenarios: list[dict[str, object]] = Field(default_factory=list)


class ChatRequest(BaseModel):
    """One assistant turn from the browser."""

    message: str = Field(min_length=1, max_length=8000)
    session: str | None = Field(default=None, max_length=200)
    context: dict[str, object] | None = None


class OptimizationRequest(BaseModel):
    """A planting optimization request."""

    sites: int = Field(default=24, ge=4, le=200)
    species: list[str] | None = None
    horizon: int = Field(default=20, ge=1, le=60)
    budget_cad: float = Field(default=60_000.0, ge=0.0)
    max_sites: int = Field(default=40, ge=1, le=500)
    generations: int = Field(default=5, ge=1, le=40)
    population: int = Field(default=20, ge=4, le=200)
    scalarizations: int = Field(default=18, ge=2, le=500)
    local_iterations: int = Field(default=120, ge=0, le=5000)
    workers: int = Field(default=2, ge=1, le=32)
    seed: int = Field(default=42, ge=0)
    surrogate_samples: int = Field(default=0, ge=0, le=500)


class SolutionSelection(BaseModel):
    """A selected archive solution."""

    solution_id: str = Field(min_length=1, max_length=40)


AGENT_GUIDE = """\
You are the FRESH Urban Forest Lab assistant. Help the user understand the current
UBC urban-forest dataset, canopy metrics, tree records, scenarios, planting
recommendations, methods, and data caveats. The web UI has a 2D map, a 3D scene,
a scenario editor, and a planting advisor.

Useful commands you may run from the repository root:
- `fresh-urban-forest info --dataset data/demo/ubc_core`
- `fresh-urban-forest detect-trees --dataset data/demo/ubc_core --out tmp/detected.geojson`
- `python -m pytest tests/test_growth_dss.py`
Read `docs/reference/methods.md` (or the RST source) and `notes/reference/data-sources.md`
when the question is methodological.

Rules:
- Use only values in the current UI context or values you obtain by running a command.
- Do not invent tree counts, canopy values, species, scenario results, or file paths.
- Do not claim you changed the UI or saved a scenario. Explain the UI steps instead.
- Be explicit that growth and carbon are estimates, not calibrated i-Tree/FVS results.
- Keep answers short and concrete; prefer short bullet lists in the narrow chat panel.
- Do not print credentials, environment secrets, or full raw data tables.
"""


@dataclass
class OptimizationJob:
    """In-memory optimization job state.

    Attributes
    ----------
    job_id : str
        Job identifier.
    status : str
        ``queued``, ``running``, ``done``, or ``error``.
    progress : int
        Completed scalarizations.
    total : int
        Requested scalarizations.
    archive_size : int
        Current archive size.
    result : object or None
        Completed optimization result.
    error : str
        Error message when the job fails.
    request : dict of str to object
        Request settings.
    started_utc : str
        Start time.
    finished_utc : str
        Finish time, or an empty string.
    """

    job_id: str
    status: str
    progress: int
    total: int
    archive_size: int
    result: object | None
    error: str
    request: dict[str, object]
    started_utc: str
    finished_utc: str = ""


@dataclass
class LabState:
    """Runtime state shared by the request handlers.

    Attributes
    ----------
    dataset : UrbanForestDataset
        Loaded dataset.
    runtime_dir : Path
        Directory for scenario JSON and export files.
    scenarios : dict of str to Scenario
        In-memory scenarios.
    results : dict of str to ScenarioResult
        Projected results.
    """

    dataset: UrbanForestDataset
    runtime_dir: Path
    scenarios: dict[str, Scenario] = field(default_factory=dict)
    results: dict[str, ScenarioResult] = field(default_factory=dict)
    tree_cache: dict[tuple[str, int], tuple[TreeRecord, ...]] = field(default_factory=dict)
    light_cache: dict[tuple[str, str, str, str], dict[str, object]] = field(default_factory=dict)
    jobs: dict[str, OptimizationJob] = field(default_factory=dict)
    allow_agent: bool = False
    agent_model: str = DEFAULT_AGENT_MODEL
    agent_timeout: float = 300.0
    workspace: Path = field(default_factory=Path.cwd)
    dataset_root: Path | None = None


def create_app(
    dataset: UrbanForestDataset,
    *,
    runtime_dir: Path | None = None,
    static_dir: Path | None = None,
    allow_agent: bool = False,
    agent_model: str = DEFAULT_AGENT_MODEL,
    agent_timeout: float = 300.0,
    workspace: Path | None = None,
    dataset_root: Path | None = None,
) -> FastAPI:
    """Create the FastAPI application.

    Parameters
    ----------
    dataset : UrbanForestDataset
        Dataset to serve.
    runtime_dir : Path or None
        Scenario directory. Defaults to ``runtime`` under the current working directory.
    static_dir : Path or None
        Optional static asset directory, used by tests.
    allow_agent : bool
        Enable the local OpenCode assistant.
    agent_model : str
        Model identifier passed to ``opencode run``.
    agent_timeout : float
        Assistant subprocess timeout in seconds.
    workspace : Path or None
        Working directory for the assistant. Defaults to the repository root.
    dataset_root : Path or None
        Dataset directory used to locate an optional observed-change product.

    Returns
    -------
    FastAPI
        Configured application.
    """
    runtime = runtime_dir or Path.cwd() / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    assistant_workspace = (workspace or Path(__file__).resolve().parents[2]).resolve()
    state = LabState(
        dataset=dataset,
        runtime_dir=runtime,
        allow_agent=allow_agent,
        agent_model=agent_model,
        agent_timeout=agent_timeout,
        workspace=assistant_workspace,
        dataset_root=dataset_root.resolve() if dataset_root is not None else None,
    )
    _load_scenarios(state)
    _load_optimizations(state)
    app = FastAPI(title="FRESH Urban Forest Lab", version="0.1.0")
    app.state.lab = state

    @app.middleware("http")
    async def no_cache_ui(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Keep the browser shell and its code from serving stale assets.

        Parameters
        ----------
        request : Request
            Incoming request.
        call_next : callable
            Downstream handler.

        Returns
        -------
        Response
            The response, with no-store headers on the shell and its code.
        """
        response = await call_next(request)
        if request.url.path in {"/", "/static/app.js", "/static/styles.css"}:
            response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    assets = static_dir or Path(__file__).resolve().parent / "web" / "static"
    if assets.exists():
        app.mount("/static", StaticFiles(directory=str(assets)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        """Return the single-page application shell."""
        path = assets / "index.html"
        if not path.exists():
            return HTMLResponse("<h1>FRESH Urban Forest Lab</h1><p>Static assets are missing.</p>")
        return HTMLResponse(path.read_text(encoding="utf-8"))

    @app.get("/api/health")
    def health() -> dict[str, object]:
        """Return a liveness and dataset summary response."""
        return {"status": "ok", "dataset_id": state.dataset.manifest.dataset_id}

    @app.get("/api/agent")
    def agent_info() -> dict[str, object]:
        """Return assistant availability and configuration.

        Returns
        -------
        dict
            Enabled flag, model, working directory, executable availability, and timeout.
        """
        return {
            "enabled": state.allow_agent,
            "model": state.agent_model,
            "cwd": str(state.workspace),
            "available": shutil.which("opencode") is not None,
            "timeout": state.agent_timeout,
        }

    @app.post("/api/agent/chat")
    def agent_chat(body: ChatRequest) -> dict[str, object]:
        """Run one assistant turn through the local OpenCode CLI.

        Parameters
        ----------
        body : ChatRequest
            User message, optional session id, and optional UI context.

        Returns
        -------
        dict
            Assistant reply, session id, and tool actions.

        Raises
        ------
        fastapi.HTTPException
            When the assistant is disabled, unavailable, times out, or returns no text.
        """
        if not state.allow_agent:
            raise HTTPException(
                status_code=403,
                detail="the assistant is disabled; start the service with --allow-agent",
            )
        executable = shutil.which("opencode")
        if executable is None:
            raise HTTPException(status_code=503, detail="opencode is not on the service PATH")
        context = json.dumps(body.context or {}, ensure_ascii=False)[:5000]
        prompt = f"{AGENT_GUIDE}\n\nCurrent UI context (JSON): {context}\n\nUser: {body.message}"
        command = [
            executable,
            "run",
            "--model",
            state.agent_model,
            "--format",
            "json",
            "--auto",
        ]
        if body.session and body.session.startswith("ses"):
            command.extend(["--session", body.session])
        command.append(prompt)
        try:
            completed = subprocess.run(
                command,
                cwd=str(state.workspace),
                env=_agent_environment(state.workspace),
                capture_output=True,
                text=True,
                timeout=state.agent_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(
                status_code=504,
                detail=f"the assistant did not answer within {state.agent_timeout:g} seconds",
            ) from exc
        except OSError as exc:
            raise HTTPException(status_code=503, detail=f"could not start opencode: {exc}") from exc
        reply, session_id, actions, errors = _parse_agent_events(completed.stdout)
        if not reply:
            detail = (
                errors[-1]
                if errors
                else (completed.stderr.strip() or "the assistant returned no text")
            )
            raise HTTPException(status_code=502, detail=detail[:500])
        return {
            "reply": reply,
            "session": session_id or body.session,
            "actions": actions,
        }

    @app.get("/api/dataset")
    def dataset_info() -> dict[str, object]:
        """Return the dataset manifest and baseline metrics."""
        return dataset_summary(state.dataset)

    @app.get("/api/completeness")
    def completeness() -> dict[str, object]:
        """Return the measured share of key tree attributes.

        Returns
        -------
        dict
            Live-tree count and measured counts/fractions by field.
        """
        return inventory_completeness(state.dataset.trees)

    @app.get("/api/changes")
    def change_products() -> dict[str, object]:
        """List optional observed-change products in the dataset.

        Returns
        -------
        dict
            Product id, labels, image version, and bounds.
        """
        products: list[dict[str, object]] = []
        if state.dataset_root is not None:
            for path in sorted(state.dataset_root.glob("change*.json")):
                if not path.is_file():
                    continue
                try:
                    payload = _read_json_object(path)
                except (OSError, ValueError):
                    continue
                products.append(
                    {
                        "id": path.name,
                        "label": f"{payload.get('earlier_label', 'earlier')} → "
                        f"{payload.get('later_label', 'later')}",
                        "image_version": payload.get("image_version", ""),
                    }
                )
        return {"products": products}

    @app.get("/api/change")
    def change_info(product: str = "change.json") -> dict[str, object]:
        """Return the optional observed-change summary.

        Returns
        -------
        dict
            The parsed ``change.json`` payload.

        Raises
        ------
        fastapi.HTTPException
            When the dataset has no change product.
        """
        path = _change_path(state, product)
        if path is None:
            raise HTTPException(status_code=404, detail="this dataset has no change product")
        payload = _read_json_object(path)
        return payload

    @app.get("/api/change.png")
    def change_png(product: str = "change.json") -> FileResponse:
        """Return the observed-change PNG overlay.

        Returns
        -------
        fastapi.responses.FileResponse
            The change PNG.

        Raises
        ------
        fastapi.HTTPException
            When the dataset has no change product.
        """
        path = _change_path(state, product)
        if path is None:
            raise HTTPException(status_code=404, detail="this dataset has no change product")
        return FileResponse(
            path.with_name(path.stem + ".png"),
            media_type="image/png",
            filename="change.png",
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    @app.get("/api/metrics")
    def baseline_metrics() -> dict[str, object]:
        """Return baseline canopy metrics."""
        metrics = state.dataset.manifest.metrics
        return _metrics_payload(metrics)

    @app.get("/api/trees")
    def trees(
        min_lon: float | None = None,
        min_lat: float | None = None,
        max_lon: float | None = None,
        max_lat: float | None = None,
        limit: int = Query(default=5000, ge=1, le=50000),
        offset: int = Query(default=0, ge=0),
        species: str | None = None,
        status: str | None = None,
    ) -> dict[str, object]:
        """Return a paginated GeoJSON tree collection.

        Parameters
        ----------
        min_lon, min_lat, max_lon, max_lat : float or None
            Optional WGS84 bounding box.
        limit : int
            Maximum features.
        offset : int
            Feature offset.
        species : str or None
            Case-insensitive species substring.
        status : str or None
            Exact status filter.

        Returns
        -------
        dict
            GeoJSON FeatureCollection with pagination metadata.
        """
        selected = list(state.dataset.trees)
        if None not in (min_lon, min_lat, max_lon, max_lat):
            selected = [
                tree
                for tree in selected
                if float(min_lon) <= tree.lon <= float(max_lon)  # type: ignore[arg-type]
                and float(min_lat) <= tree.lat <= float(max_lat)  # type: ignore[arg-type]
            ]
        if species:
            text = species.lower()
            selected = [
                tree
                for tree in selected
                if text in tree.species.lower() or text in tree.common_name.lower()
            ]
        if status:
            selected = [tree for tree in selected if tree.status == status]
        total = len(selected)
        page = selected[offset : offset + limit]
        return {
            "type": "FeatureCollection",
            "features": [_tree_feature(tree) for tree in page],
            "total": total,
            "returned": len(page),
            "offset": offset,
        }

    @app.get("/api/scene")
    def scene(
        scenario_id: str | None = None,
        year: int | None = Query(default=None, ge=0, le=100),
    ) -> dict[str, object]:
        """Return the scene payload for the baseline or a projected scenario.

        Parameters
        ----------
        scenario_id : str or None
            Optional scenario identifier.
        year : int or None
            Optional projection year. ``None`` uses the scenario horizon; zero shows the
            edited baseline.

        Returns
        -------
        dict
            Scene payload.
        """
        if scenario_id:
            result = _ensure_result(state, scenario_id)
            target = result.scenario.years if year is None else year
            if 0 <= target < len(result.tree_timeline):
                return build_scene(state.dataset, result.tree_timeline[target])
            key = (scenario_id, target)
            if key not in state.tree_cache:
                scenario = _scenario_or_404(state, scenario_id)
                state.tree_cache[key] = project_trees_to_year(
                    state.dataset,
                    scenario,
                    target,
                )
            return build_scene(state.dataset, state.tree_cache[key])
        return build_scene(state.dataset)

    @app.get("/api/canopy.png")
    def canopy_png(width: int = Query(default=1024, ge=128, le=2048)) -> Response:
        """Render the canopy-height grid as a transparent PNG overlay.

        Parameters
        ----------
        width : int
            Output image width in pixels.

        Returns
        -------
        fastapi.responses.Response
            PNG image.
        """
        return Response(
            content=_canopy_png(state.dataset, width),
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    @app.get("/api/hillshade.png")
    def hillshade_png(width: int = Query(default=1024, ge=128, le=2048)) -> Response:
        """Render a hillshade of the terrain grid.

        Parameters
        ----------
        width : int
            Output image width in pixels.

        Returns
        -------
        fastapi.responses.Response
            PNG image.
        """
        return Response(
            content=_hillshade_png(state.dataset, width),
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    @app.get("/api/solar")
    def solar(
        date: str | None = Query(default=None),
        time: str = Query(default="12:00"),
        timezone: str = Query(default=DEFAULT_TIMEZONE),
    ) -> dict[str, object]:
        """Return the solar position for one date and time.

        Parameters
        ----------
        date : str or None
            ISO date. Defaults to today.
        time : str
            Clock time, such as ``14:30``.
        timezone : str
            IANA timezone name.

        Returns
        -------
        dict
            Solar position and daylight metadata.

        Raises
        ------
        fastapi.HTTPException
            When the date or time is invalid.
        """
        try:
            day = parse_date(date) if date else dt.date.today()
            when = dt.datetime.combine(day, parse_clock(time), tzinfo=_zone(timezone))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        left, bottom, right, top = state.dataset.terrain.bounds
        lon, lat = unproject_xy(
            (left + right) / 2.0, (bottom + top) / 2.0, state.dataset.terrain.crs
        )
        position = solar_position(when, lon, lat)
        return {
            "date": day.isoformat(),
            "time": time,
            "timezone": timezone,
            "position": position.to_dict(),
        }

    @app.get("/api/shade")
    def shade(
        date: str | None = Query(default=None),
        mode: Literal["instant", "day", "annual"] = Query(default="day"),
        times: str | None = Query(default=None),
        target_height_m: float = Query(default=1.5, ge=0.1, le=20.0),
        include_terrain: bool = Query(default=True),
    ) -> dict[str, object]:
        """Return a shaded-area summary for a date and time mode.

        Parameters
        ----------
        date : str or None
            ISO date. Defaults to today.
        mode : str
            ``instant``, ``day``, or ``annual``.
        times : str or None
            Comma-separated clock times.
        target_height_m : float
            Height above ground of the target plane.
        include_terrain : bool
            Include the coarse terrain horizon.

        Returns
        -------
        dict
            Metrics, solar positions, image corners, legend, and evidence.
        """
        day, whens, step = _shade_whens(date, mode, times)
        period = shade_period(
            state.dataset,
            whens,
            target_height_m=target_height_m,
            step_hours=step,
            include_terrain=include_terrain,
        )
        return _shade_payload(state.dataset, period, day=day, mode=mode, timezone=DEFAULT_TIMEZONE)

    @app.get("/api/shade.png")
    def shade_image(
        date: str | None = Query(default=None),
        mode: Literal["instant", "day", "annual"] = Query(default="day"),
        times: str | None = Query(default=None),
        target_height_m: float = Query(default=1.5, ge=0.1, le=20.0),
        include_terrain: bool = Query(default=True),
    ) -> Response:
        """Return the aggregated shade overlay as a PNG.

        Parameters
        ----------
        date : str or None
            ISO date. Defaults to today.
        mode : str
            ``instant``, ``day``, or ``annual``.
        times : str or None
            Comma-separated clock times.
        target_height_m : float
            Height above ground of the target plane.
        include_terrain : bool
            Include the coarse terrain horizon.

        Returns
        -------
        fastapi.responses.Response
            PNG image with no-store caching.
        """
        _, whens, step = _shade_whens(date, mode, times)
        period = shade_period(
            state.dataset,
            whens,
            target_height_m=target_height_m,
            step_hours=step,
            include_terrain=include_terrain,
        )
        return Response(
            content=shade_png(period),
            media_type="image/png",
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    @app.get("/api/light/tree/{tree_id}")
    def tree_light(
        tree_id: str,
        date: str | None = Query(default=None),
        mode: Literal["instant", "day", "annual"] = Query(default="day"),
        times: str | None = Query(default=None),
    ) -> dict[str, object]:
        """Return the shade, species, water, irrigation, and growth cards for one tree.

        Parameters
        ----------
        tree_id : str
            Tree identifier.
        date : str or None
            ISO date. Defaults to today.
        mode : str
            ``instant``, ``day``, or ``annual``.
        times : str or None
            Comma-separated clock times.

        Returns
        -------
        dict
            A tree-level light and water card.

        Raises
        ------
        fastapi.HTTPException
            When the tree does not exist or has no projected coordinates.
        """
        tree = _tree_or_404(state.dataset, tree_id)
        day, whens, step = _shade_whens(date, mode, times)
        key = (tree_id, day.isoformat(), mode, times or "")
        cached = state.light_cache.get(key)
        if cached is not None:
            return cached
        card = shade_at_tree(
            state.dataset,
            tree,
            whens,
            step_hours=step,
            include_terrain=True,
        )
        sun_fraction = float(str(card["sun_fraction_at_base"]))
        crown_width = max(float(tree.crown_width_m or 6.0), 0.5)
        crown_area = math.pi * (crown_width / 2.0) ** 2
        soil_volume = max(1.0, crown_area * 0.45)
        profile = profile_for_species(tree.species or tree.common_name)
        fit = site_fit(
            profile,
            sun_fraction=sun_fraction,
            soil_volume_m3=soil_volume,
            water_availability=0.55,
            heat_exposure=max(0.0, 1.0 - sun_fraction) * 0.4 + 0.3,
            space_available_m=max(crown_width * 1.4, 4.0),
        )
        irrigation = compare_irrigation(
            profile,
            crown_area_m2=crown_area,
            soil_volume_m3=soil_volume,
            sun_fraction=sun_fraction,
            shade_area_hours=float(str(card["marginal_shade_area_hours"])),
            age_years=10.0,
        )
        water = next(
            (option.balance for option in irrigation if option.recommendation == "best balance"),
            irrigation[0].balance,
        )
        response = growth_response(
            profile,
            sun_fraction=sun_fraction,
            water=water,
            soil_volume_m3=soil_volume,
            heat_exposure=max(0.0, 1.0 - sun_fraction) * 0.4 + 0.3,
        )
        growth = project_species_growth(
            profile,
            response,
            initial_dbh_cm=float(tree.dbh_cm or 6.0),
            years=20,
        )
        payload: dict[str, object] = {
            "tree": _tree_feature(tree)["properties"],
            "shade": card,
            "species": profile.to_dict(),
            "fit": fit.to_dict(),
            "water": water.to_dict(),
            "irrigation": [option.to_dict() for option in irrigation],
            "growth": growth.to_dict(),
            "assumptions": {
                "soil_volume_m3": round(soil_volume, 2),
                "crown_area_m2": round(crown_area, 2),
                "sun_fraction": round(sun_fraction, 3),
                "date": day.isoformat(),
                "mode": mode,
            },
        }
        state.light_cache[key] = payload
        return payload

    @app.get("/api/species")
    def species_profiles() -> dict[str, object]:
        """Return the built-in species trait profiles.

        Returns
        -------
        dict
            Profiles and the shared evidence note.
        """
        return {
            "profiles": [profile.to_dict() for profile in all_profiles()],
            "evidence": all_profiles()[0].source if all_profiles() else "",
        }

    @app.get("/api/species/fit")
    def species_fit(
        species: str = Query(default="Acer rubrum"),
        sun_fraction: float = Query(default=0.6, ge=0.0, le=1.0),
        soil_volume_m3: float = Query(default=6.0, ge=0.1, le=100.0),
        water_availability: float = Query(default=0.55, ge=0.0, le=1.0),
        heat_exposure: float = Query(default=0.5, ge=0.0, le=1.0),
        space_available_m: float = Query(default=10.0, ge=0.1, le=100.0),
    ) -> dict[str, object]:
        """Return a species site-fit card.

        Parameters
        ----------
        species : str
            Species name.
        sun_fraction : float
            Fraction of daylight the site is sunlit.
        soil_volume_m3 : float
            Available soil volume.
        water_availability : float
            Relative water availability.
        heat_exposure : float
            Relative heat exposure.
        space_available_m : float
            Available growing space.

        Returns
        -------
        dict
            Profile and fit.
        """
        profile = profile_for_species(species)
        fit = site_fit(
            profile,
            sun_fraction=sun_fraction,
            soil_volume_m3=soil_volume_m3,
            water_availability=water_availability,
            heat_exposure=heat_exposure,
            space_available_m=space_available_m,
        )
        return {"profile": profile.to_dict(), "fit": fit.to_dict()}

    @app.get("/api/water")
    def water(
        species: str = Query(default="Acer rubrum"),
        sun_fraction: float = Query(default=0.6, ge=0.0, le=1.0),
        soil_volume_m3: float = Query(default=6.0, ge=0.1, le=100.0),
        crown_area_m2: float = Query(default=20.0, ge=0.5, le=400.0),
        age_years: float = Query(default=10.0, ge=0.0, le=100.0),
        policy: Literal["none", "establishment", "fixed", "moisture_trigger", "deficit"] = Query(
            default="moisture_trigger"
        ),
    ) -> dict[str, object]:
        """Return one annual tree water balance.

        Parameters
        ----------
        species : str
            Species name.
        sun_fraction : float
            Fraction of daylight the site is sunlit.
        soil_volume_m3 : float
            Available soil volume.
        crown_area_m2 : float
            Projected crown area.
        age_years : float
            Tree age.
        policy : str
            Irrigation policy.

        Returns
        -------
        dict
            Water balance and policy comparison.
        """
        profile = profile_for_species(species)
        balance = simulate_water_balance(
            profile,
            crown_area_m2=crown_area_m2,
            soil_volume_m3=soil_volume_m3,
            sun_fraction=sun_fraction,
            policy=policy,
            age_years=age_years,
        )
        options = compare_water_policies(
            profile,
            crown_area_m2=crown_area_m2,
            soil_volume_m3=soil_volume_m3,
            sun_fraction=sun_fraction,
            age_years=age_years,
        )
        return {
            "balance": balance.to_dict(),
            "policies": [option.to_dict() for option in options],
        }

    @app.get("/api/irrigation")
    def irrigation(
        species: str = Query(default="Acer rubrum"),
        sun_fraction: float = Query(default=0.6, ge=0.0, le=1.0),
        soil_volume_m3: float = Query(default=6.0, ge=0.1, le=100.0),
        crown_area_m2: float = Query(default=20.0, ge=0.5, le=400.0),
        shade_area_hours: float = Query(default=1000.0, ge=0.0),
        age_years: float = Query(default=10.0, ge=0.0, le=100.0),
    ) -> dict[str, object]:
        """Return irrigation options and cost per effective shade-hour.

        Parameters
        ----------
        species : str
            Species name.
        sun_fraction : float
            Fraction of daylight the site is sunlit.
        soil_volume_m3 : float
            Available soil volume.
        crown_area_m2 : float
            Projected crown area.
        shade_area_hours : float
            Effective shade area-hours supported by the tree.
        age_years : float
            Tree age.

        Returns
        -------
        dict
            Ranked irrigation options.
        """
        profile = profile_for_species(species)
        options = compare_irrigation(
            profile,
            crown_area_m2=crown_area_m2,
            soil_volume_m3=soil_volume_m3,
            sun_fraction=sun_fraction,
            shade_area_hours=shade_area_hours,
            age_years=age_years,
        )
        return {"options": [option.to_dict() for option in options]}

    @app.get("/api/optimize")
    def list_optimizations() -> dict[str, object]:
        """List optimization jobs.

        Returns
        -------
        dict
            Job summaries, newest last.
        """
        return {"jobs": [_job_payload(job) for job in state.jobs.values()]}

    @app.post("/api/optimize", status_code=202)
    def start_optimization(payload: OptimizationRequest) -> dict[str, object]:
        """Start a background planting optimization.

        Parameters
        ----------
        payload : OptimizationRequest
            Problem and solver settings.

        Returns
        -------
        dict
            Job summary.

        Raises
        ------
        fastapi.HTTPException
            When the optional optimization extra is unavailable.
        """
        if not _optimizer_available():
            raise HTTPException(
                status_code=503,
                detail="the optimizer requires the optimize extra: pip install -e '.[optimize]'",
            )
        job_id = f"opt-{uuid.uuid4().hex[:10]}"
        request_payload = payload.model_dump()
        job = OptimizationJob(
            job_id=job_id,
            status="queued",
            progress=0,
            total=payload.scalarizations,
            archive_size=0,
            result=None,
            error="",
            request=request_payload,
            started_utc=_utc_now(),
        )
        state.jobs[job_id] = job
        thread = threading.Thread(target=_run_optimization_job, args=(state, job_id), daemon=True)
        thread.start()
        return _job_payload(job)

    @app.get("/api/optimize/{job_id}")
    def optimization_job(job_id: str) -> dict[str, object]:
        """Return one optimization job.

        Parameters
        ----------
        job_id : str
            Job identifier.

        Returns
        -------
        dict
            Job state and, when done, the full result.

        Raises
        ------
        fastapi.HTTPException
            When the job does not exist.
        """
        job = state.jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="optimization job not found")
        return _job_payload(job, include_result=True)

    @app.get("/api/optimize/{job_id}/solutions")
    def optimization_solutions(job_id: str) -> dict[str, object]:
        """Return the Pareto archive for a completed job.

        Parameters
        ----------
        job_id : str
            Job identifier.

        Returns
        -------
        dict
            Archive with solutions, ideal/nadir, hypervolume, and robustness.

        Raises
        ------
        fastapi.HTTPException
            When the job is missing or not done.
        """
        job = state.jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="optimization job not found")
        if job.result is None:
            raise HTTPException(status_code=409, detail="optimization job is still running")
        result = job.result
        archive = getattr(result, "archive", None)
        if archive is None or not hasattr(archive, "to_dict"):
            raise HTTPException(status_code=500, detail="optimization archive is unavailable")
        archive_payload = archive.to_dict()
        if not isinstance(archive_payload, Mapping):
            raise HTTPException(status_code=500, detail="optimization archive is malformed")
        return {str(key): value for key, value in archive_payload.items()}

    @app.post("/api/optimize/{job_id}/scenario", status_code=201)
    def optimization_scenario(job_id: str, payload: SolutionSelection) -> dict[str, object]:
        """Load one archive solution as a scenario.

        Parameters
        ----------
        job_id : str
            Job identifier.
        payload : SolutionSelection
            Selected solution identifier.

        Returns
        -------
        dict
            The created scenario.

        Raises
        ------
        fastapi.HTTPException
            When the job, solution, or archive is unavailable.
        """
        from fresh_urban_forest.optimize import solution_to_edits

        job = state.jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="optimization job not found")
        if job.result is None:
            raise HTTPException(status_code=409, detail="optimization job is still running")
        result = job.result
        archive = getattr(result, "archive", None)
        solutions = getattr(archive, "solutions", ())
        solution = next(
            (item for item in solutions if getattr(item, "solution_id", "") == payload.solution_id),
            None,
        )
        if solution is None:
            raise HTTPException(status_code=404, detail="solution not found")
        problem = getattr(result, "problem", None)
        if problem is None:
            raise HTTPException(status_code=500, detail="problem is unavailable")
        scenario_id = f"scenario-{uuid.uuid4().hex[:10]}"
        scenario = Scenario(
            scenario_id=scenario_id,
            name=f"Pareto {payload.solution_id[:8]}",
            created_utc=_utc_now(),
            base_dataset_id=state.dataset.manifest.dataset_id,
            years=int(getattr(problem, "horizon", 20)),
            edits=solution_to_edits(problem, solution),
        )
        state.scenarios[scenario_id] = scenario
        _save_scenario(state, scenario)
        return _scenario_payload(scenario)

    @app.get("/api/scenario-comparison")
    def scenario_comparison() -> dict[str, object]:
        """Project and compare all saved scenarios.

        Returns
        -------
        dict
            Compact baseline/final metrics, score, and cost for every scenario.
        """
        rows: list[dict[str, object]] = []
        for scenario in state.scenarios.values():
            result = _ensure_result(state, scenario.scenario_id)
            baseline = result.metrics_by_year[0][1]
            final = result.metrics_by_year[-1][1]
            rows.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "name": scenario.name,
                    "years": scenario.years,
                    "edits": len(scenario.edits),
                    "cost_cad": result.cost,
                    "score": result.score,
                    "baseline_cover_pct": baseline.canopy_cover_pct,
                    "final_cover_pct": final.canopy_cover_pct,
                    "final_volume_m3": final.canopy_volume_m3,
                    "final_carbon_kg": final.total_carbon_kg,
                    "final_native_fraction": final.native_fraction,
                }
            )
        rows.sort(key=lambda row: float(str(row["score"])), reverse=True)
        return {"scenarios": rows}

    @app.get("/api/scenarios")
    def list_scenarios() -> dict[str, object]:
        """Return scenario metadata and cached scores."""
        return {
            "scenarios": [
                {
                    **_scenario_summary(scenario),
                    "score": state.results[scenario.scenario_id].score
                    if scenario.scenario_id in state.results
                    else None,
                }
                for scenario in state.scenarios.values()
            ]
        }

    @app.post("/api/scenarios", status_code=201)
    def create_scenario(payload: ScenarioInput) -> dict[str, object]:
        """Create a scenario.

        Parameters
        ----------
        payload : ScenarioInput
            Scenario name, horizon, and initial edits.

        Returns
        -------
        dict
            The scenario summary.
        """
        scenario_id = f"scenario-{uuid.uuid4().hex[:10]}"
        scenario = Scenario(
            scenario_id=scenario_id,
            name=payload.name,
            created_utc=_utc_now(),
            base_dataset_id=state.dataset.manifest.dataset_id,
            years=payload.years,
            edits=tuple(_edit_from_input(edit) for edit in payload.edits),
        )
        state.scenarios[scenario_id] = scenario
        _save_scenario(state, scenario)
        return _scenario_payload(scenario)

    @app.get("/api/scenarios/{scenario_id}")
    def get_scenario(scenario_id: str) -> dict[str, object]:
        """Return one scenario and its edits.

        Parameters
        ----------
        scenario_id : str
            Scenario identifier.

        Returns
        -------
        dict
            Scenario payload.
        """
        return _scenario_payload(_scenario_or_404(state, scenario_id))

    @app.patch("/api/scenarios/{scenario_id}")
    def append_edits(scenario_id: str, payload: ScenarioPatch) -> dict[str, object]:
        """Append edits to a scenario.

        Parameters
        ----------
        scenario_id : str
            Scenario identifier.
        payload : ScenarioPatch
            New edits and an optional expected revision.

        Returns
        -------
        dict
            Updated scenario payload.
        """
        scenario = _scenario_or_404(state, scenario_id)
        if payload.revision is not None and payload.revision != scenario.revision:
            raise HTTPException(status_code=409, detail="scenario revision changed")
        updated = Scenario(
            scenario_id=scenario.scenario_id,
            name=scenario.name,
            created_utc=scenario.created_utc,
            base_dataset_id=scenario.base_dataset_id,
            years=scenario.years,
            edits=scenario.edits + tuple(_edit_from_input(edit) for edit in payload.edits),
            revision=scenario.revision + 1,
        )
        state.scenarios[scenario_id] = updated
        state.results.pop(scenario_id, None)
        for key in [key for key in state.tree_cache if key[0] == scenario_id]:
            state.tree_cache.pop(key, None)
        _save_scenario(state, updated)
        return _scenario_payload(updated)

    @app.post("/api/scenarios/{scenario_id}/project")
    def project(scenario_id: str) -> dict[str, object]:
        """Project a scenario and return its summary.

        Parameters
        ----------
        scenario_id : str
            Scenario identifier.

        Returns
        -------
        dict
            Timeline, final metrics, cost, and score.
        """
        result = _ensure_result(state, scenario_id)
        return scenario_summary(result)

    @app.get("/api/scenarios/{scenario_id}/result")
    def result(scenario_id: str) -> dict[str, object]:
        """Return a projected scenario, projecting it if needed.

        Parameters
        ----------
        scenario_id : str
            Scenario identifier.

        Returns
        -------
        dict
            Timeline, final metrics, cost, score, and metric deltas.
        """
        result_value = _ensure_result(state, scenario_id)
        summary = scenario_summary(result_value)
        summary["deltas"] = metric_delta(
            result_value.metrics_by_year[0][1], result_value.metrics_by_year[-1][1]
        )
        return summary

    @app.get("/api/scenarios/{scenario_id}/compare")
    def compare(scenario_id: str) -> dict[str, object]:
        """Compare a scenario against the baseline and every other cached scenario.

        Parameters
        ----------
        scenario_id : str
            Scenario identifier.

        Returns
        -------
        dict
            Baseline deltas and scenario ranking.
        """
        result_value = _ensure_result(state, scenario_id)
        baseline = state.dataset.manifest.metrics
        final = result_value.metrics_by_year[-1][1]
        return {
            "scenario_id": scenario_id,
            "baseline_deltas": compare_metrics(baseline, final),
            "ranking": [
                {"scenario_id": item_id, "score": score}
                for item_id, score in compare_scenarios(list(state.results.values())).ranking
            ],
        }

    @app.post("/api/dss/recommend")
    def recommend(payload: PlantingRequest) -> dict[str, object]:
        """Return ranked planting candidates and ready-to-apply edits.

        Parameters
        ----------
        payload : PlantingRequest
            Recommendation settings.

        Returns
        -------
        dict
            Candidates, plant edits, and the assumed unit cost.
        """
        center = (
            (payload.center_lon, payload.center_lat)
            if payload.center_lon is not None and payload.center_lat is not None
            else None
        )
        candidates = recommend_planting(
            state.dataset,
            count=payload.count,
            species=payload.species,
            budget_cad=payload.budget_cad,
            grid_m=payload.grid_m,
            center_lonlat=center,
            radius_m=payload.radius_m,
        )
        edits = candidates_to_edits(
            candidates,
            species=payload.species,
            common_name=payload.common_name or payload.species,
            dbh_cm=6.0,
        )
        return {
            "candidates": [
                {
                    "lon": candidate.lon,
                    "lat": candidate.lat,
                    "score": candidate.score,
                    "canopy_height_m": candidate.canopy_height_m,
                    "slope_percent": candidate.slope_percent,
                    "nearest_tree_m": candidate.nearest_tree_m,
                    "reasons": list(candidate.reasons),
                }
                for candidate in candidates
            ],
            "edits": [edit_to_dict(edit) for edit in edits],
            "unit_cost_cad": 750.0,
        }

    @app.get("/api/scenarios/{scenario_id}/export.geojson")
    def export_geojson(scenario_id: str) -> FileResponse:
        """Export the final tree population as GeoJSON.

        Parameters
        ----------
        scenario_id : str
            Scenario identifier.

        Returns
        -------
        fastapi.responses.FileResponse
            Download response.
        """
        result_value = _ensure_result(state, scenario_id)
        path = state.runtime_dir / "exports" / f"{scenario_id}.geojson"
        export_scenario_geojson(result_value, path)
        return FileResponse(path, media_type="application/geo+json", filename=path.name)

    @app.get("/api/scenarios/{scenario_id}/export.csv")
    def export_csv(scenario_id: str) -> FileResponse:
        """Export the scenario timeline as CSV.

        Parameters
        ----------
        scenario_id : str
            Scenario identifier.

        Returns
        -------
        fastapi.responses.FileResponse
            Download response.
        """
        result_value = _ensure_result(state, scenario_id)
        path = state.runtime_dir / "exports" / f"{scenario_id}.csv"
        export_scenario_csv(result_value, path)
        return FileResponse(path, media_type="text/csv", filename=path.name)

    return app


def _shade_whens(
    date_value: str | None,
    mode: Literal["instant", "day", "annual"],
    times_value: str | None,
) -> tuple[dt.date, tuple[dt.datetime, ...], float]:
    """Build the sample times for a shade request.

    Parameters
    ----------
    date_value : str or None
        ISO date, or ``None`` for today.
    mode : str
        ``instant``, ``day``, or ``annual``.
    times_value : str or None
        Comma-separated clock times.

    Returns
    -------
    tuple
        Date, aware datetimes, and step hours.

    Raises
    ------
    fastapi.HTTPException
        When the date or a time is invalid.
    """
    try:
        day = parse_date(date_value) if date_value else dt.date.today()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if mode == "annual":
        return (
            day,
            representative_time_grid(day.year),
            3.0,
        )
    raw = [part.strip() for part in (times_value or "").split(",") if part.strip()]
    if not raw:
        raw = ["12:00"] if mode == "instant" else list(DEFAULT_TIMES)
    if mode == "instant":
        raw = raw[:1]
    try:
        whens = time_grid(day, times=raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    step = 1.0 if mode == "instant" else default_step_hours(whens)
    return (day, whens, step)


def _shade_payload(
    dataset: UrbanForestDataset,
    period: ShadePeriod,
    *,
    day: dt.date,
    mode: str,
    timezone: str,
) -> dict[str, object]:
    """Build the JSON payload for a shade period.

    Parameters
    ----------
    dataset : UrbanForestDataset
        Dataset that supplies the image corners.
    period : ShadePeriod
        Aggregated period.
    day : datetime.date
        Requested date.
    mode : str
        Requested mode.
    timezone : str
        IANA timezone name.

    Returns
    -------
    dict
        Period summary plus georeferencing, legend, and evidence.
    """
    payload = period.to_dict()
    left, bottom, right, top = dataset.terrain.bounds
    lon, lat = unproject_xy((left + right) / 2.0, (bottom + top) / 2.0, dataset.terrain.crs)
    payload.update(
        {
            "date": day.isoformat(),
            "solar": [solar_position(when, lon, lat).to_dict() for when in period.whens],
            "mode": mode,
            "timezone": timezone,
            "bounds": list(dataset.terrain.bounds),
            "image_corners_wgs84": _grid_corners(dataset),
            "legend": [
                {"label": "building shade", "colour": "#2b5eaa"},
                {"label": "tree shade", "colour": "#2d7d48"},
                {"label": "overlap", "colour": "#183644"},
                {"label": "terrain shade", "colour": "#5a5a5a"},
            ],
        }
    )
    return payload


def _grid_corners(dataset: UrbanForestDataset) -> list[list[float]]:
    """Return the image corners in MapLibre order.

    Parameters
    ----------
    dataset : UrbanForestDataset
        Dataset that supplies the terrain bounds.

    Returns
    -------
    list of list of float
        Top-left, top-right, bottom-right, and bottom-left in WGS84.
    """
    left, bottom, right, top = dataset.terrain.bounds
    return [
        list(unproject_xy(x, y, dataset.terrain.crs))
        for x, y in ((left, top), (right, top), (right, bottom), (left, bottom))
    ]


def _tree_or_404(dataset: UrbanForestDataset, tree_id: str) -> TreeRecord:
    """Return a tree or raise a 404.

    Parameters
    ----------
    dataset : UrbanForestDataset
        Dataset to search.
    tree_id : str
        Tree identifier.

    Returns
    -------
    TreeRecord
        The tree.

    Raises
    ------
    fastapi.HTTPException
        When the tree does not exist.
    """
    for tree in dataset.trees:
        if tree.tree_id == tree_id:
            return tree
    raise HTTPException(status_code=404, detail="tree not found")


def _optimizer_available() -> bool:
    """Return whether the optional optimizer extra is importable.

    Returns
    -------
    bool
        ``True`` when the Fresh Solutions-backed optimizer imports.
    """
    try:
        import fresh_urban_forest.optimize  # noqa: F401
    except Exception:
        return False
    return True


def _job_payload(job: OptimizationJob, *, include_result: bool = False) -> dict[str, object]:
    """Convert a job to a JSON-safe payload.

    Parameters
    ----------
    job : OptimizationJob
        Job state.
    include_result : bool
        Include the full result when it exists.

    Returns
    -------
    dict
        Job summary.
    """
    payload: dict[str, object] = {
        "job_id": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "total": job.total,
        "archive_size": job.archive_size,
        "hypervolume": (
            float(getattr(getattr(job.result, "archive", None), "hypervolume", 0.0))
            if job.result is not None
            else 0.0
        ),
        "error": job.error,
        "request": dict(job.request),
        "started_utc": job.started_utc,
        "finished_utc": job.finished_utc,
    }
    if include_result and job.result is not None and hasattr(job.result, "to_dict"):
        payload["result"] = job.result.to_dict()
    return payload


def _run_optimization_job(state: LabState, job_id: str) -> None:
    """Run one optimization job in a daemon thread.

    Parameters
    ----------
    state : LabState
        Application state.
    job_id : str
        Job identifier.
    """
    job = state.jobs.get(job_id)
    if job is None:
        return
    try:
        from fresh_urban_forest.optimize import build_problem, run_optimization

        request = job.request
        raw_species = request.get("species")
        species = (
            tuple(str(value) for value in raw_species) if isinstance(raw_species, list) else None
        )
        job.status = "running"
        job.started_utc = _utc_now()
        problem = build_problem(
            state.dataset,
            site_count=_request_int(request, "sites", 24),
            species=species,
            horizon=_request_int(request, "horizon", 20),
            budget_cad=_request_float(request, "budget_cad", 60_000.0),
            max_sites=_request_int(request, "max_sites", 40),
            seed=_request_int(request, "seed", 42),
        )

        def progress(done: int, total: int, archive_size: int) -> None:
            job.progress = done
            job.total = total
            job.archive_size = archive_size

        result = run_optimization(
            problem,
            population_size=_request_int(request, "population", 20),
            generations=_request_int(request, "generations", 5),
            scalarizations=_request_int(request, "scalarizations", 18),
            local_iterations=_request_int(request, "local_iterations", 120),
            workers=_request_int(request, "workers", 2),
            seed=_request_int(request, "seed", 42),
            surrogate_samples=_request_int(request, "surrogate_samples", 0),
            progress=progress,
        )
        job.result = result
        job.archive_size = len(getattr(getattr(result, "archive", None), "solutions", ()))
        try:
            _save_optimization_result(state, job_id, result)
        except OSError as exc:
            job.error = f"result could not be saved: {exc}"
        job.status = "done"
    except Exception as exc:
        job.status = "error"
        job.error = str(exc)[:500]
    finally:
        job.finished_utc = _utc_now()


def _save_optimization_result(state: LabState, job_id: str, result: object) -> None:
    """Persist a completed optimization result for later UI loading.

    Parameters
    ----------
    state : LabState
        Application state.
    job_id : str
        Job identifier.
    result : object
        Optimization result with a ``to_dict`` method.
    """
    if not hasattr(result, "to_dict"):
        return
    directory = state.runtime_dir / OPTIMIZATION_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{job_id}.json"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(result.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _load_optimizations(state: LabState) -> None:
    """Load saved optimization results from the runtime directory.

    Parameters
    ----------
    state : LabState
        Application state to populate.
    """
    from fresh_urban_forest.optimize import result_from_dict

    directory = state.runtime_dir / OPTIMIZATION_DIR
    if not directory.exists():
        return
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, Mapping):
                continue
            result = result_from_dict(payload)
        except (OSError, ValueError, KeyError, TypeError):
            continue
        problem = result.problem
        request_payload = {
            "sites": len(problem.sites),
            "species": [option.name for option in problem.species],
            "horizon": problem.horizon,
            "budget_cad": problem.budget_cad,
            "max_sites": problem.max_sites,
            "seed": problem.seed,
            "scalarizations": result.scalarizations,
        }
        state.jobs[path.stem] = OptimizationJob(
            job_id=path.stem,
            status="done",
            progress=result.scalarizations,
            total=result.scalarizations,
            archive_size=len(result.archive.solutions),
            result=result,
            error="",
            request=request_payload,
            started_utc="",
            finished_utc="",
        )


def _request_int(request: Mapping[str, object], key: str, default: int) -> int:
    """Read an integer request field.

    Parameters
    ----------
    request : mapping
        Request payload.
    key : str
        Field key.
    default : int
        Fallback.

    Returns
    -------
    int
        Parsed value.
    """
    value = request.get(key, default)
    if isinstance(value, (int, float, str)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    return default


def _request_float(request: Mapping[str, object], key: str, default: float) -> float:
    """Read a float request field.

    Parameters
    ----------
    request : mapping
        Request payload.
    key : str
        Field key.
    default : float
        Fallback.

    Returns
    -------
    float
        Parsed value.
    """
    value = request.get(key, default)
    if isinstance(value, (int, float, str)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
    return default


def _zone(name: str) -> ZoneInfo:
    """Return a timezone, falling back to UTC.

    Parameters
    ----------
    name : str
        IANA timezone name.

    Returns
    -------
    zoneinfo.ZoneInfo
        The timezone.
    """
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")


def _read_json_object(path: Path) -> dict[str, object]:
    """Read a JSON file and require a top-level object.

    Parameters
    ----------
    path : Path
        JSON file.

    Returns
    -------
    dict
        The parsed object.

    Raises
    ------
    fastapi.HTTPException
        When the payload is not a JSON object.
    """
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail="change summary is not a JSON object")
    return {str(key): value for key, value in payload.items()}


def _change_path(state: LabState, product: str = "change.json") -> Path | None:
    """Return a validated change summary path.

    Parameters
    ----------
    state : LabState
        Application state.
    product : str
        Change product filename, such as ``change.json`` or
        ``change_2015_2021.json``.

    Returns
    -------
    Path or None
        The path when it is a safe, existing ``change*.json`` file.
    """
    if state.dataset_root is None:
        return None
    name = Path(product).name
    if not name.startswith("change") or not name.endswith(".json"):
        return None
    path = state.dataset_root / name
    return path if path.is_file() else None


def _agent_environment(workspace: Path) -> dict[str, str]:
    """Build a sanitized environment for the assistant subprocess.

    Parameters
    ----------
    workspace : Path
        Repository root that supplies the package source.

    Returns
    -------
    dict of str to str
        Environment variables with session and cloud credentials removed.
    """
    environment = dict(os.environ)
    paths = [str(workspace / "src")]
    if environment.get("PYTHONPATH"):
        paths.append(environment["PYTHONPATH"])
    environment["PYTHONPATH"] = os.pathsep.join(paths)
    environment["FRESH_URBAN_FOREST_WORKSPACE"] = str(workspace)
    for name in (
        "OPENCODE_SESSION_ID",
        "OPENCODE_TERMINAL",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_DEFAULT_REGION",
        "S3_ENDPOINT_URL",
        "GLOBUS_ACCESS_TOKEN",
        "GLOBUS_REFRESH_TOKEN",
    ):
        environment.pop(name, None)
    return environment


def _parse_agent_events(stdout: str) -> tuple[str, str | None, list[dict[str, str]], list[str]]:
    """Parse the JSON-lines output of ``opencode run --format json``.

    Parameters
    ----------
    stdout : str
        Captured standard output.

    Returns
    -------
    tuple
        Reply text, session id, tool actions, and error messages.
    """
    texts: list[str] = []
    actions: list[dict[str, str]] = []
    errors: list[str] = []
    session_id: str | None = None
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, Mapping):
            continue
        candidate = event.get("sessionID")
        if isinstance(candidate, str) and candidate.startswith("ses"):
            session_id = candidate
        event_type = event.get("type")
        if event_type == "error":
            failure = event.get("error")
            if isinstance(failure, Mapping) and isinstance(failure.get("message"), str):
                errors.append(str(failure["message"]))
            continue
        part = event.get("part")
        if not isinstance(part, Mapping):
            continue
        if event_type == "text":
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())
        elif event_type == "tool_use":
            tool = part.get("tool")
            state = part.get("state")
            summary = ""
            if isinstance(state, Mapping):
                title = state.get("title")
                if isinstance(title, str):
                    summary = title
                inputs = state.get("input")
                if isinstance(inputs, Mapping):
                    for key in ("command", "filePath", "path", "pattern", "url", "description"):
                        value = inputs.get(key)
                        if isinstance(value, str) and value.strip():
                            summary = value.strip()
                            break
            if isinstance(tool, str):
                action = {"tool": tool, "summary": summary[:160]}
                if action not in actions:
                    actions.append(action)
    return "\n\n".join(texts).strip(), session_id, actions[-12:], errors


def _load_scenarios(state: LabState) -> None:
    """Load scenario JSON files from the runtime directory.

    Parameters
    ----------
    state : LabState
        Application state to populate.
    """
    directory = state.runtime_dir / "scenarios"
    if not directory.exists():
        return
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            scenario = scenario_from_dict(payload)
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
        state.scenarios[scenario.scenario_id] = scenario


def _save_scenario(state: LabState, scenario: Scenario) -> None:
    """Atomically persist a scenario.

    Parameters
    ----------
    state : LabState
        Application state.
    scenario : Scenario
        Scenario to save.
    """
    directory = state.runtime_dir / "scenarios"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{scenario.scenario_id}.json"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(scenario_to_dict(scenario), indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _scenario_or_404(state: LabState, scenario_id: str) -> Scenario:
    """Return a scenario or raise a 404.

    Parameters
    ----------
    state : LabState
        Application state.
    scenario_id : str
        Scenario identifier.

    Returns
    -------
    Scenario
        The scenario.

    Raises
    ------
    fastapi.HTTPException
        When the scenario does not exist.
    """
    scenario = state.scenarios.get(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="scenario not found")
    return scenario


def _ensure_result(state: LabState, scenario_id: str) -> ScenarioResult:
    """Project a scenario once and cache the result.

    Parameters
    ----------
    state : LabState
        Application state.
    scenario_id : str
        Scenario identifier.

    Returns
    -------
    ScenarioResult
        Projected result.
    """
    if scenario_id in state.results:
        return state.results[scenario_id]
    scenario = _scenario_or_404(state, scenario_id)
    result_value = project_scenario(state.dataset, scenario, collect_trees=True)
    state.results[scenario_id] = result_value
    return result_value


def _edit_from_input(edit: EditInput) -> ScenarioEdit:
    """Convert an API edit to a typed scenario edit.

    Parameters
    ----------
    edit : EditInput
        API edit.

    Returns
    -------
    ScenarioEdit
        Typed edit with a generated identifier.
    """
    return ScenarioEdit(
        edit_id=f"edit-{uuid.uuid4().hex[:10]}",
        kind=edit.kind,
        tree_id=edit.tree_id,
        lon=edit.lon,
        lat=edit.lat,
        species=edit.species,
        common_name=edit.common_name,
        dbh_cm=edit.dbh_cm,
        height_m=edit.height_m,
        crown_width_m=edit.crown_width_m,
        note=edit.note,
    )


def _scenario_payload(scenario: Scenario) -> dict[str, object]:
    """Convert a scenario to an API payload.

    Parameters
    ----------
    scenario : Scenario
        Scenario to convert.

    Returns
    -------
    dict
        JSON-safe scenario.
    """
    return {
        **_scenario_summary(scenario),
        "edits": [edit_to_dict(edit) for edit in scenario.edits],
    }


def _scenario_summary(scenario: Scenario) -> dict[str, object]:
    """Return the non-edit fields of a scenario.

    Parameters
    ----------
    scenario : Scenario
        Scenario to summarise.

    Returns
    -------
    dict
        Scenario metadata.
    """
    return {
        "scenario_id": scenario.scenario_id,
        "name": scenario.name,
        "created_utc": scenario.created_utc,
        "base_dataset_id": scenario.base_dataset_id,
        "years": scenario.years,
        "revision": scenario.revision,
        "edit_count": len(scenario.edits),
    }


def _metrics_payload(metrics: CanopyMetrics) -> dict[str, object]:
    """Convert metrics to an API payload.

    Parameters
    ----------
    metrics : CanopyMetrics
        Metrics to convert.

    Returns
    -------
    dict
        JSON-safe metrics.
    """
    return {
        "tree_count": metrics.tree_count,
        "species_count": metrics.species_count,
        "native_fraction": metrics.native_fraction,
        "canopy_cover_pct": metrics.canopy_cover_pct,
        "canopy_volume_m3": metrics.canopy_volume_m3,
        "mean_height_m": metrics.mean_height_m,
        "p95_height_m": metrics.p95_height_m,
        "total_carbon_kg": metrics.total_carbon_kg,
        "shannon_index": metrics.shannon_index,
        "size_classes": [list(item) for item in metrics.size_classes],
        "species_composition": [list(item) for item in metrics.species_composition],
    }


def _tree_feature(tree: TreeRecord) -> dict[str, object]:
    """Convert a tree to a GeoJSON feature.

    Parameters
    ----------
    tree : TreeRecord
        Tree to convert.

    Returns
    -------
    dict
        GeoJSON feature.
    """
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [tree.lon, tree.lat]},
        "properties": {
            "tree_id": tree.tree_id,
            "species": tree.species,
            "common_name": tree.common_name,
            "dbh_cm": tree.dbh_cm,
            "height_m": tree.height_m,
            "crown_width_m": tree.crown_width_m,
            "status": tree.status,
            "native": tree.native,
            "source": tree.source,
        },
    }


def _canopy_png(dataset: UrbanForestDataset, width: int) -> bytes:
    """Render a canopy-height PNG.

    Parameters
    ----------
    dataset : UrbanForestDataset
        Dataset with a canopy-height grid.
    width : int
        Output width.

    Returns
    -------
    bytes
        PNG bytes.
    """
    grid = dataset.terrain
    canopy = (
        grid.canopy_height
        if grid.canopy_height is not None
        else np.zeros((grid.height, grid.width))
    )
    height = max(1, round(width * grid.height / max(grid.width, 1)))
    image = Image.fromarray(_canopy_rgba(np.asarray(canopy, dtype=np.float32))).resize(
        (width, height), Image.Resampling.BILINEAR
    )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _hillshade_png(dataset: UrbanForestDataset, width: int) -> bytes:
    """Render a terrain hillshade PNG.

    Parameters
    ----------
    dataset : UrbanForestDataset
        Dataset with an elevation grid.
    width : int
        Output width.

    Returns
    -------
    bytes
        PNG bytes.
    """
    grid = dataset.terrain
    elevation = np.asarray(grid.elevation, dtype=np.float64)
    grad_y, grad_x = np.gradient(elevation)
    slope = np.pi / 2.0 - np.arctan(np.hypot(grad_x, grad_y))
    aspect = np.arctan2(-grad_x, grad_y)
    azimuth = math.radians(315.0)
    altitude = math.radians(45.0)
    shade = np.sin(altitude) * np.sin(slope) + np.cos(altitude) * np.cos(slope) * np.cos(
        azimuth - aspect
    )
    shade = np.clip((shade + 1.0) / 2.0, 0.0, 1.0)
    rgba = (shade * 255.0).astype(np.uint8)
    image = Image.fromarray(rgba, mode="L").convert("RGBA")
    height = max(1, round(width * grid.height / max(grid.width, 1)))
    image = image.resize((width, height), Image.Resampling.BILINEAR)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _canopy_rgba(canopy: np.ndarray) -> np.ndarray:
    """Map canopy height to an RGBA array.

    Parameters
    ----------
    canopy : numpy.ndarray
        Canopy height in metres.

    Returns
    -------
    numpy.ndarray
        ``(rows, columns, 4)`` uint8 array.
    """
    clipped = np.clip(np.nan_to_num(canopy, nan=0.0), 0.0, 45.0)
    normalized = clipped / 45.0
    red = 0.95 - 0.55 * normalized
    green = 0.78 + 0.18 * np.sin(np.pi * normalized)
    blue = 0.24 + 0.18 * normalized
    alpha = np.where(clipped >= 1.0, 205.0, 0.0)
    rgba = np.stack([red * 255.0, green * 255.0, blue * 255.0, alpha], axis=-1)
    return rgba.astype(np.uint8)


def _utc_now() -> str:
    """Return the current UTC timestamp.

    Returns
    -------
    str
        ISO timestamp.
    """
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
