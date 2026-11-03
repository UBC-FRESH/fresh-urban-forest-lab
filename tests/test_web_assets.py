"""Static checks that keep the browser shell honest without a browser."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "fresh_urban_forest" / "web" / "static"


def test_static_shell_has_required_hooks() -> None:
    """The shell names the mount points, tabs, and controls the script expects."""
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    for marker in (
        "map",
        "scene-canvas",
        "timeline-chart",
        "plant-tree",
        "recommend",
        'data-view="scene"',
    ):
        assert marker in html
    assert "static/vendor/maplibre-gl.js" in html
    assert 'href="/static' not in html
    assert "importmap" in html


def test_app_script_has_the_expected_endpoints_and_layers() -> None:
    """The script calls the documented endpoints and uses instanced crowns."""
    script = (STATIC / "app.js").read_text(encoding="utf-8")
    for marker in (
        "/api/dataset",
        "/api/scene",
        "/api/scenarios",
        "/api/dss/recommend",
        "InstancedMesh",
        "OrbitControls",
        "maplibregl.Map",
        "api/agent/chat",
        "renderAssistantMarkdown",
        "ExtrudeGeometry",
        "base_z",
        "renderChangeStats",
    ):
        assert marker in script
    assert "eval(" not in script


def test_vendored_assets_are_present() -> None:
    """The offline assets needed by the shell are committed."""
    for relative in (
        "vendor/maplibre-gl.js",
        "vendor/maplibre-gl.css",
        "vendor/three/three.module.js",
        "vendor/three/OrbitControls.js",
    ):
        path = STATIC / relative
        assert path.exists()
        assert path.stat().st_size > 1000
