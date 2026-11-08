"""Contract tests for the FastAPI service."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from fresh_urban_forest.service import create_app
from tests.fixtures import make_dataset


def _client(tmp_path: Path) -> TestClient:
    """Build a test client over a synthetic dataset."""
    dataset = make_dataset(tmp_path)
    return TestClient(
        create_app(
            dataset,
            runtime_dir=tmp_path / "runtime",
            dataset_root=tmp_path / "dataset",
        )
    )


def test_health_dataset_metrics_and_trees(tmp_path: Path) -> None:
    """Core read endpoints return the dataset and filtered trees."""
    client = _client(tmp_path)
    assert client.get("/api/health").json()["status"] == "ok"
    dataset = client.get("/api/dataset").json()
    assert dataset["tree_count"] > 0
    metrics = client.get("/api/metrics").json()
    assert metrics["tree_count"] > 0
    completeness = client.get("/api/completeness").json()
    assert completeness["total"] > 0
    assert "dbh" in completeness["fields"]
    trees = client.get("/api/trees", params={"limit": 3}).json()
    assert trees["returned"] == 3
    assert trees["total"] > 3
    species = client.get("/api/trees", params={"species": "thuja"}).json()
    assert all("Thuja" in feature["properties"]["species"] for feature in species["features"])
    removed = client.get("/api/trees", params={"status": "removed"}).json()
    assert removed["returned"] == 0
    bbox = client.get(
        "/api/trees",
        params={"min_lon": -180, "min_lat": -90, "max_lon": 180, "max_lat": 90, "limit": 1},
    ).json()
    assert bbox["returned"] == 1


def test_city_metrics_endpoint_is_optional(tmp_path: Path) -> None:
    """A dataset without a city pack returns 404; adding one serves it."""
    client = _client(tmp_path)
    assert client.get("/api/city-metrics").status_code == 404
    (tmp_path / "dataset" / "city_metrics.json").write_text(
        '{"city": {"tree_count": 2}, "local_areas": []}', encoding="utf-8"
    )
    response = client.get("/api/city-metrics")
    assert response.status_code == 200
    assert response.json()["city"]["tree_count"] == 2


def test_heat_priority_endpoints_are_optional(tmp_path: Path) -> None:
    """A dataset without the product returns 404; adding it serves JSON and GeoJSON."""
    client = _client(tmp_path)
    assert client.get("/api/heat-priority").status_code == 404
    assert client.get("/api/heat-priority.geojson").status_code == 404
    (tmp_path / "dataset" / "heat_priority.json").write_text(
        '{"schema_version": "test", "metadata": {}, "cells": []}', encoding="utf-8"
    )
    (tmp_path / "dataset" / "heat_priority.geojson").write_text(
        '{"type": "FeatureCollection", "features": []}', encoding="utf-8"
    )
    dataset = client.get("/api/dataset").json()
    assert dataset["has_heat_priority"] is True
    response = client.get("/api/heat-priority")
    assert response.status_code == 200
    assert response.json()["schema_version"] == "test"
    geojson = client.get("/api/heat-priority.geojson")
    assert geojson.status_code == 200
    assert geojson.headers["content-type"].startswith("application/geo+json")


def test_canopy_turnover_endpoints_are_optional(tmp_path: Path) -> None:
    """A dataset without the product returns 404; adding it serves JSON and GeoJSON."""
    client = _client(tmp_path)
    assert client.get("/api/canopy-turnover").status_code == 404
    assert client.get("/api/canopy-turnover.geojson").status_code == 404
    (tmp_path / "dataset" / "canopy_turnover.json").write_text(
        '{"schema_version": "test", "metadata": {}, "cells": []}', encoding="utf-8"
    )
    (tmp_path / "dataset" / "canopy_turnover.geojson").write_text(
        '{"type": "FeatureCollection", "features": []}', encoding="utf-8"
    )
    dataset = client.get("/api/dataset").json()
    assert dataset["has_canopy_turnover"] is True
    response = client.get("/api/canopy-turnover")
    assert response.status_code == 200
    assert response.json()["schema_version"] == "test"
    geojson = client.get("/api/canopy-turnover.geojson")
    assert geojson.status_code == 200
    assert geojson.headers["content-type"].startswith("application/geo+json")


def test_canopy_action_endpoints_are_optional(tmp_path: Path) -> None:
    """A dataset without the product returns 404; adding it serves JSON and GeoJSON."""
    client = _client(tmp_path)
    assert client.get("/api/canopy-action").status_code == 404
    assert client.get("/api/canopy-action.geojson").status_code == 404
    (tmp_path / "dataset" / "canopy_action.json").write_text(
        '{"schema_version": "test", "metadata": {}, "cells": []}', encoding="utf-8"
    )
    (tmp_path / "dataset" / "canopy_action.geojson").write_text(
        '{"type": "FeatureCollection", "features": []}', encoding="utf-8"
    )
    dataset = client.get("/api/dataset").json()
    assert dataset["has_canopy_action"] is True
    response = client.get("/api/canopy-action")
    assert response.status_code == 200
    assert response.json()["schema_version"] == "test"
    geojson = client.get("/api/canopy-action.geojson")
    assert geojson.status_code == 200
    assert geojson.headers["content-type"].startswith("application/geo+json")


def test_canopy_change_endpoints_are_optional(tmp_path: Path) -> None:
    """A dataset without the product returns 404; adding it serves JSON and GeoJSON."""
    client = _client(tmp_path)
    assert client.get("/api/canopy-change").status_code == 404
    assert client.get("/api/canopy-change.geojson").status_code == 404
    (tmp_path / "dataset" / "canopy_change.json").write_text(
        '{"schema_version": "test", "metadata": {}, "cells": []}', encoding="utf-8"
    )
    (tmp_path / "dataset" / "canopy_change.geojson").write_text(
        '{"type": "FeatureCollection", "features": []}', encoding="utf-8"
    )
    dataset = client.get("/api/dataset").json()
    assert dataset["has_canopy_change"] is True
    response = client.get("/api/canopy-change")
    assert response.status_code == 200
    assert response.json()["schema_version"] == "test"
    geojson = client.get("/api/canopy-change.geojson")
    assert geojson.status_code == 200
    assert geojson.headers["content-type"].startswith("application/geo+json")


def test_heat_equity_endpoints_are_optional(tmp_path: Path) -> None:
    """A dataset without the product returns 404; adding it serves JSON and GeoJSON."""
    client = _client(tmp_path)
    assert client.get("/api/heat-equity").status_code == 404
    assert client.get("/api/heat-equity.geojson").status_code == 404
    (tmp_path / "dataset" / "heat_equity.json").write_text(
        '{"schema_version": "test", "metadata": {}, "cells": []}', encoding="utf-8"
    )
    (tmp_path / "dataset" / "heat_equity.geojson").write_text(
        '{"type": "FeatureCollection", "features": []}', encoding="utf-8"
    )
    dataset = client.get("/api/dataset").json()
    assert dataset["has_heat_equity"] is True
    response = client.get("/api/heat-equity")
    assert response.status_code == 200
    assert response.json()["schema_version"] == "test"
    geojson = client.get("/api/heat-equity.geojson")
    assert geojson.status_code == 200
    assert geojson.headers["content-type"].startswith("application/geo+json")


def test_planting_opportunity_endpoints_are_optional(tmp_path: Path) -> None:
    """A dataset without the product returns 404; adding it serves JSON and GeoJSON."""
    client = _client(tmp_path)
    assert client.get("/api/planting-opportunity").status_code == 404
    assert client.get("/api/planting-opportunity.geojson").status_code == 404
    (tmp_path / "dataset" / "planting_opportunity.json").write_text(
        '{"schema_version": "test", "metadata": {}, "cells": []}', encoding="utf-8"
    )
    (tmp_path / "dataset" / "planting_opportunity.geojson").write_text(
        '{"type": "FeatureCollection", "features": []}', encoding="utf-8"
    )
    dataset = client.get("/api/dataset").json()
    assert dataset["has_planting_opportunity"] is True
    response = client.get("/api/planting-opportunity")
    assert response.status_code == 200
    assert response.json()["schema_version"] == "test"
    geojson = client.get("/api/planting-opportunity.geojson")
    assert geojson.status_code == 200
    assert geojson.headers["content-type"].startswith("application/geo+json")


def test_full_map_layers_are_optional(tmp_path: Path) -> None:
    """The compressed full map layers are served when present."""
    import gzip

    client = _client(tmp_path)
    assert client.get("/api/map-trees").status_code == 404
    (tmp_path / "dataset" / "map_trees.json.gz").write_bytes(
        gzip.compress(b'{"type":"FeatureCollection","features":[]}')
    )
    (tmp_path / "dataset" / "map_buildings.geojson.gz").write_bytes(
        gzip.compress(b'{"type":"FeatureCollection","features":[]}')
    )
    (tmp_path / "dataset" / "full_scene.json.gz").write_bytes(gzip.compress(b'{"compact":true}'))
    (tmp_path / "dataset" / "roads.geojson.gz").write_bytes(
        gzip.compress(b'{"type":"FeatureCollection","features":[]}')
    )
    dataset = client.get("/api/dataset").json()
    assert dataset["has_map_trees"] is True
    assert dataset["has_map_buildings"] is True
    assert dataset["has_full_scene"] is True
    assert dataset["has_roads"] is True
    assert client.get("/api/full-scene").status_code == 200
    assert client.get("/api/roads").status_code == 200
    response = client.get("/api/map-trees")
    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"


def test_scene_and_image_endpoints(tmp_path: Path) -> None:
    """Scene and PNG endpoints return usable payloads."""
    client = _client(tmp_path)
    scene = client.get("/api/scene").json()
    assert "terrain" in scene
    assert "trees" in scene
    canopy = client.get("/api/canopy.png", params={"width": 128})
    assert canopy.status_code == 200
    assert canopy.headers["content-type"] == "image/png"
    assert canopy.content.startswith(b"\x89PNG")
    hillshade = client.get("/api/hillshade.png", params={"width": 128})
    assert hillshade.status_code == 200
    assert hillshade.content.startswith(b"\x89PNG")


def test_scenario_lifecycle(tmp_path: Path) -> None:
    """A scenario can be created, patched, projected, compared, and exported."""
    client = _client(tmp_path)
    first_tree = client.get("/api/trees", params={"limit": 1}).json()["features"][0]["properties"]
    created = client.post(
        "/api/scenarios",
        json={
            "name": "Test scenario",
            "years": 3,
            "edits": [{"kind": "remove", "tree_id": first_tree["tree_id"]}],
        },
    )
    assert created.status_code == 201
    scenario = created.json()
    scenario_id = scenario["scenario_id"]
    assert scenario["edit_count"] == 1
    patched = client.patch(
        f"/api/scenarios/{scenario_id}",
        json={
            "revision": scenario["revision"],
            "edits": [
                {
                    "kind": "plant",
                    "tree_id": "plant:test",
                    "lon": -123.25,
                    "lat": 49.26,
                    "species": "Acer macrophyllum",
                    "dbh_cm": 6.0,
                }
            ],
        },
    )
    assert patched.status_code == 200
    assert patched.json()["revision"] == 1
    conflict = client.patch(f"/api/scenarios/{scenario_id}", json={"revision": 0, "edits": []})
    assert conflict.status_code == 409
    listed = client.get("/api/scenarios").json()
    assert listed["scenarios"]
    projected = client.post(f"/api/scenarios/{scenario_id}/project")
    assert projected.status_code == 200
    assert len(projected.json()["timeline"]) == 4
    result = client.get(f"/api/scenarios/{scenario_id}/result").json()
    assert "deltas" in result
    compared = client.get(f"/api/scenarios/{scenario_id}/compare").json()
    assert compared["ranking"]
    scene = client.get("/api/scene", params={"scenario_id": scenario_id}).json()
    assert len(scene["trees"]) >= len(client.get("/api/scene").json()["trees"])
    csv = client.get(f"/api/scenarios/{scenario_id}/export.csv")
    assert csv.status_code == 200
    assert csv.text.startswith("year,")
    geojson = client.get(f"/api/scenarios/{scenario_id}/export.geojson")
    assert geojson.status_code == 200
    assert geojson.json()["type"] == "FeatureCollection"


def test_scenario_year_scene_and_comparison(tmp_path: Path) -> None:
    """A scene can be requested at a projection year and scenarios can be compared."""
    client = _client(tmp_path)
    created = client.post(
        "/api/scenarios",
        json={
            "name": "Year scene",
            "years": 5,
            "edits": [
                {
                    "kind": "plant",
                    "tree_id": "plant:year",
                    "lon": -123.25,
                    "lat": 49.26,
                    "species": "Acer macrophyllum",
                    "dbh_cm": 6.0,
                }
            ],
        },
    ).json()
    scenario_id = created["scenario_id"]
    client.post(f"/api/scenarios/{scenario_id}/project")
    scene_zero = client.get("/api/scene", params={"scenario_id": scenario_id, "year": 0}).json()
    scene_five = client.get("/api/scene", params={"scenario_id": scenario_id, "year": 5}).json()
    zero_tree = next(tree for tree in scene_zero["trees"] if tree["id"] == "plant:year")
    five_tree = next(tree for tree in scene_five["trees"] if tree["id"] == "plant:year")
    assert five_tree["height"] > zero_tree["height"]
    comparison = client.get("/api/scenario-comparison").json()
    assert comparison["scenarios"][0]["scenario_id"] == scenario_id
    assert comparison["scenarios"][0]["final_cover_pct"] > 0


def test_recommend_and_not_found(tmp_path: Path) -> None:
    """The recommender returns edits and unknown scenarios are 404."""
    client = _client(tmp_path)
    response = client.post(
        "/api/dss/recommend",
        json={"count": 5, "species": "Acer macrophyllum", "budget_cad": 5000},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["edits"]
    assert payload["candidates"]
    center = payload["candidates"][0]
    centered = client.post(
        "/api/dss/recommend",
        json={
            "count": 3,
            "species": "Acer macrophyllum",
            "center_lon": center["lon"],
            "center_lat": center["lat"],
            "radius_m": 50,
        },
    )
    assert centered.status_code == 200
    assert centered.json()["candidates"]
    assert client.get("/api/scenarios/missing").status_code == 404
    assert client.get("/api/scenarios/missing/result").status_code == 404


def test_change_endpoints_when_a_product_exists(tmp_path: Path) -> None:
    """The service exposes the optional change summary and PNG."""
    import json

    import numpy as np

    from fresh_urban_forest.change_product import build_change_product
    from fresh_urban_forest.models import TerrainGrid

    dataset = make_dataset(tmp_path)
    earlier = np.array(dataset.terrain.elevation, dtype=np.float32)
    later = earlier + 1.0
    grid_earlier = TerrainGrid(
        crs=dataset.terrain.crs,
        bounds=dataset.terrain.bounds,
        width=dataset.terrain.width,
        height=dataset.terrain.height,
        elevation=dataset.terrain.elevation,
        canopy_height=earlier,
    )
    grid_later = TerrainGrid(
        crs=dataset.terrain.crs,
        bounds=dataset.terrain.bounds,
        width=dataset.terrain.width,
        height=dataset.terrain.height,
        elevation=dataset.terrain.elevation,
        canopy_height=later,
    )
    build_change_product(grid_earlier, grid_later, tmp_path / "dataset")
    client = TestClient(
        create_app(dataset, runtime_dir=tmp_path / "runtime", dataset_root=tmp_path / "dataset")
    )
    summary = client.get("/api/change")
    assert summary.status_code == 200
    assert json.loads(summary.text)["metrics"]["threshold_m"] == 2.0
    products = client.get("/api/changes").json()
    assert products["products"]
    assert products["products"][0]["id"] == "change.json"
    png = client.get("/api/change.png")
    assert png.status_code == 200
    assert png.content.startswith(b"\x89PNG")
    assert client.get("/api/change").json()["legend"]


def test_change_endpoint_is_404_without_a_product(tmp_path: Path) -> None:
    """A dataset without an observed-change product returns 404."""
    client = _client(tmp_path)
    assert client.get("/api/change").status_code == 404
    assert client.get("/api/change.png").status_code == 404


def test_index_serves_the_shell(tmp_path: Path) -> None:
    """The root route serves the single-page shell."""
    client = _client(tmp_path)
    response = client.get("/")
    assert response.status_code == 200
    assert "FRESH Urban Forest Lab" in response.text


def test_light_solar_shade_species_and_water_endpoints(tmp_path: Path) -> None:
    """The light and species endpoints return coherent, evidence-labelled payloads."""
    client = _client(tmp_path)
    solar = client.get("/api/solar", params={"date": "2026-06-21", "time": "12:00"})
    assert solar.status_code == 200
    assert solar.json()["position"]["is_daylight"] is True
    shade = client.get(
        "/api/shade",
        params={"date": "2026-06-21", "mode": "day", "times": "09:00,12:00,15:00"},
    )
    assert shade.status_code == 200
    metrics = shade.json()["metrics"]
    assert abs(metrics["sunlit_fraction"] + metrics["shade_fraction"] - 1.0) < 1e-6
    assert shade.json()["legend"]
    png = client.get(
        "/api/shade.png",
        params={"date": "2026-06-21", "mode": "day", "times": "09:00,12:00,15:00"},
    )
    assert png.status_code == 200
    assert png.content.startswith(b"\x89PNG")
    profiles = client.get("/api/species").json()["profiles"]
    assert len(profiles) >= 10
    fit = client.get("/api/species/fit", params={"species": "Acer rubrum"}).json()
    assert "fit" in fit
    assert "profile" in fit
    water = client.get("/api/water", params={"species": "Acer rubrum"}).json()
    assert water["balance"]["policy"] == "moisture_trigger"
    assert len(water["policies"]) == 5
    irrigation = client.get("/api/irrigation", params={"species": "Acer rubrum"}).json()
    assert len(irrigation["options"]) == 5
    card = client.get(
        "/api/light/tree/test:2",
        params={"date": "2026-06-21", "mode": "day", "times": "09:00,12:00,15:00"},
    )
    assert card.status_code == 200
    payload = card.json()
    assert payload["shade"]["tree_id"] == "test:2"
    assert payload["fit"]["species"] == "Acer rubrum"
    assert payload["growth"]["points"]
    assert payload["irrigation"]
    cached = client.get(
        "/api/light/tree/test:2",
        params={"date": "2026-06-21", "mode": "day", "times": "09:00,12:00,15:00"},
    )
    assert cached.status_code == 200
    assert client.get("/api/light/tree/missing").status_code == 404
    assert client.get("/api/shade", params={"date": "not-a-date"}).status_code == 400


def test_optimization_job_and_scenario(tmp_path: Path) -> None:
    """An optimization job runs, exposes solutions, and loads one as a scenario."""
    import time

    client = _client(tmp_path)
    started = client.post(
        "/api/optimize",
        json={
            "sites": 6,
            "species": ["Acer rubrum", "Thuja plicata"],
            "horizon": 5,
            "population": 6,
            "generations": 1,
            "scalarizations": 4,
            "local_iterations": 10,
            "workers": 1,
            "seed": 3,
        },
    )
    assert started.status_code == 202
    job_id = started.json()["job_id"]
    payload = {}
    for _ in range(80):
        response = client.get(f"/api/optimize/{job_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"done", "error"}:
            break
        time.sleep(0.1)
    assert payload["status"] == "done", payload.get("error")
    assert payload["archive_size"] > 0
    assert payload["result"]["archive"]["solutions"]
    solutions = client.get(f"/api/optimize/{job_id}/solutions")
    assert solutions.status_code == 200
    solution_id = solutions.json()["solutions"][0]["solution_id"]
    scenario = client.post(
        f"/api/optimize/{job_id}/scenario",
        json={"solution_id": solution_id},
    )
    assert scenario.status_code == 201
    assert scenario.json()["scenario_id"].startswith("scenario-")
    assert client.get("/api/optimize").json()["jobs"]
    assert client.get("/api/optimize/missing").status_code == 404
    saved = tmp_path / "runtime" / "optimizations" / f"{job_id}.json"
    assert saved.exists()
    dataset = make_dataset(tmp_path / "reload")
    reloaded = TestClient(
        create_app(
            dataset,
            runtime_dir=tmp_path / "runtime",
            dataset_root=tmp_path / "reload" / "dataset",
        )
    )
    assert any(job["job_id"] == job_id for job in reloaded.get("/api/optimize").json()["jobs"])
    restored = reloaded.get(f"/api/optimize/{job_id}")
    assert restored.status_code == 200
    assert restored.json()["result"]["archive"]["solutions"]
    renamed = client.patch(f"/api/optimize/{job_id}", json={"name": "Renamed archive"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Renamed archive"
    deleted = client.delete(f"/api/optimize/{job_id}")
    assert deleted.status_code == 200
    assert not saved.exists()


def test_off_inventory_endpoints(tmp_path: Path) -> None:
    """The off-inventory report, GeoJSON, and value-of-information endpoints work."""
    import json

    client = _client(tmp_path)
    root = tmp_path / "dataset"
    (root / "off_inventory.json").write_text(
        json.dumps(
            {
                "schema_version": "fresh-urban-forest.off-inventory.v1",
                "candidate_count": 1,
                "candidates": [],
            }
        ),
        encoding="utf-8",
    )
    (root / "off_inventory.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": []}),
        encoding="utf-8",
    )
    (root / "off_inventory_voi.json").write_text(
        json.dumps({"plan_jaccard": 1.0, "changed_sites": 0}),
        encoding="utf-8",
    )
    report = client.get("/api/off-inventory")
    assert report.status_code == 200
    assert report.json()["candidate_count"] == 1
    geojson = client.get("/api/off-inventory.geojson")
    assert geojson.status_code == 200
    assert geojson.json()["type"] == "FeatureCollection"
    value = client.get("/api/off-inventory/value")
    assert value.status_code == 200
    assert value.json()["plan_jaccard"] == 1.0


def test_off_inventory_gzip_endpoint(tmp_path: Path) -> None:
    """A compressed candidate layer is served with Content-Encoding: gzip."""
    import gzip
    import json

    client = _client(tmp_path)
    root = tmp_path / "dataset"
    (root / "off_inventory.json").write_text(
        json.dumps({"candidate_count": 1, "candidates": []}), encoding="utf-8"
    )
    with gzip.open(root / "off_inventory.geojson.gz", "wt", encoding="utf-8") as handle:
        json.dump({"type": "FeatureCollection", "features": []}, handle)
    response = client.get("/api/off-inventory.geojson")
    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"
    assert response.json() == {"type": "FeatureCollection", "features": []}
    with gzip.open(root / "off_inventory_3d.json.gz", "wt", encoding="utf-8") as handle:
        json.dump({"count": 1, "x_m": [0.0], "y_m": [0.0]}, handle)
    compact = client.get("/api/off-inventory-3d")
    assert compact.status_code == 200
    assert compact.headers["content-encoding"] == "gzip"
    assert compact.json()["count"] == 1


def test_classifier_endpoint(tmp_path: Path) -> None:
    """The classifier report is served only when present."""
    import json

    client = _client(tmp_path)
    root = tmp_path / "dataset"
    report = {"model_family": "test", "evaluation": {"accuracy": 0.8}}
    (root / "classifier_report.json").write_text(json.dumps(report), encoding="utf-8")
    response = client.get("/api/classifier")
    assert response.status_code == 200
    assert response.json()["evaluation"]["accuracy"] == 0.8


def test_bird_habitat_and_demography_endpoint(tmp_path: Path) -> None:
    """The bird endpoint returns structural metrics, guilds, and prior demography."""
    client = _client(tmp_path)
    response = client.get("/api/birds")
    assert response.status_code == 200
    payload = response.json()
    assert payload["metrics"]["tree_count"] > 0
    assert len(payload["guilds"]) == 5
    assert 0.0 <= payload["metrics"]["habitat_score"] <= 1.0
    guild = payload["guilds"][0]
    assert 0.0 <= guild["suitability"] <= 1.0
    assert guild["relative_abundance_index"] >= 0.0
    assert guild["demography"]["lambda"] > 0.0
    assert guild["demography"]["prior_range"][0] <= guild["demography"]["lambda"]
    assert "not a density" in payload["caveat"]


def test_lab_report_endpoint(tmp_path: Path) -> None:
    """The unified report includes metrics, shade, and birds."""
    client = _client(tmp_path)
    response = client.get("/api/report")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "fresh-urban-forest.lab-report.v1"
    assert payload["metrics"]["tree_count"] > 0
    assert "shade" in payload
    assert "birds" in payload
    assert payload["evidence"]
