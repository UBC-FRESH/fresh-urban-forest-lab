"""Tests for the UBC/Vancouver landing portal."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from fresh_urban_forest.portal import PortalDemo, create_portal_app
from tests.fixtures import make_dataset


def test_portal_mounts_both_demos(tmp_path: Path) -> None:
    """The landing page and both mounted apps answer under their slugs."""
    make_dataset(tmp_path / "ubc")
    make_dataset(tmp_path / "city")
    app = create_portal_app(
        (
            PortalDemo(
                slug="ubc",
                label="UBC campus",
                subtitle="campus",
                dataset_root=tmp_path / "ubc" / "dataset",
                runtime_dir=tmp_path / "runtime" / "ubc",
                description="campus demo",
            ),
            PortalDemo(
                slug="city",
                label="Vancouver city",
                subtitle="city",
                dataset_root=tmp_path / "city" / "dataset",
                runtime_dir=tmp_path / "runtime" / "city",
                description="city demo",
            ),
        )
    )
    client = TestClient(app)
    landing = client.get("/")
    assert landing.status_code == 200
    assert "UBC campus" in landing.text
    assert "Vancouver city" in landing.text
    assert client.get("/ubc/api/health").json()["status"] == "ok"
    assert client.get("/city/api/health").json()["status"] == "ok"
    assert client.get("/ubc/").status_code == 200
    assert client.get("/city/").status_code == 200
    assert client.get("/ubc/static/app.js").status_code == 200
    demos = client.get("/api/demos").json()
    assert [item["slug"] for item in demos["demos"]] == ["ubc", "city"]
    assert client.get("/health").json()["demos"] == ["ubc", "city"]
