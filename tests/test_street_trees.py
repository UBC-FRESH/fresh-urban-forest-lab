"""Tests for the street-level tree candidate geometry and provider."""

from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path

import httpx

from fresh_urban_forest.street_trees import (
    KartaViewClient,
    StreetImage,
    bearing_offset_deg,
    candidates_geojson,
    detection_from_box,
    fuse_detections,
    match_inventory,
    project_pixel,
)


def _image(**overrides: object) -> StreetImage:
    """Return a test image with defaults."""
    values: dict[str, object] = {
        "provider": "test",
        "image_id": "image-1",
        "lon": -123.1,
        "lat": 49.25,
        "heading_deg": 0.0,
        "width": 1000,
        "height": 750,
        "captured_at": "2026-01-01",
        "image_url": "https://example.test/image.jpg",
        "license": "CC BY-SA 4.0",
        "attribution": "test",
        "horizontal_fov_deg": 60.0,
        "fov_source": "assumed",
    }
    values.update(overrides)
    # The helper accepts mixed override types; each override is validated by the dataclass.
    return StreetImage(**values)  # type: ignore[arg-type]


def test_center_pixel_projects_north() -> None:
    """A centre pixel with a north heading lands north of the camera."""
    lon, lat = project_pixel(_image(), 500.0, 10.0)
    assert lon == -123.1
    assert math.isclose(lat, 49.25 + 10.0 / 110_540.0, rel_tol=0, abs_tol=1e-12)


def test_bearing_offset_is_positive_to_the_right() -> None:
    """Off-centre pixels on the right have positive bearing offsets."""
    assert bearing_offset_deg(500.0, 1000, 60.0) == 0.0
    assert bearing_offset_deg(750.0, 1000, 60.0) > 0.0
    assert bearing_offset_deg(250.0, 1000, 60.0) < 0.0


def test_detection_box_projects_bottom_centre() -> None:
    """The box helper creates a projected detection with a bounded score."""
    image = _image()
    detection = detection_from_box(image, (400.0, 500.0, 600.0, 700.0), score=1.5, depth_m=8.0)
    assert detection.image_id == "image-1"
    assert detection.score == 1.0
    assert detection.depth_m == 8.0
    assert detection.lon == image.lon


def test_fusion_combines_same_tree_views() -> None:
    """Nearby detections become one candidate with multiple views."""
    first = detection_from_box(_image(), (400.0, 500.0, 600.0, 700.0), score=0.7, depth_m=8.0)
    second = detection_from_box(
        _image(image_id="image-2"),
        (405.0, 505.0, 605.0, 705.0),
        score=0.9,
        depth_m=8.1,
    )
    candidates = fuse_detections((first, second), radius_m=6.0)
    assert len(candidates) == 1
    assert candidates[0].view_count == 2
    assert candidates[0].score == 0.9
    assert candidates[0].candidate_id.startswith("street:image-1:")


def test_fusion_links_points_across_grid_cells() -> None:
    """Spatial bucketing does not miss a pair that straddles a cell boundary."""
    base = detection_from_box(_image(), (400.0, 500.0, 600.0, 700.0), score=0.8, depth_m=8.0)
    east_per_degree = 111_320.0 * math.cos(math.radians(base.lat))
    first = replace(base, lon=base.lon + 5.9 / east_per_degree, lat=base.lat + 0.1 / 110_540.0)
    second = replace(
        base,
        image_id="image-2",
        lon=base.lon + 6.1 / east_per_degree,
        lat=base.lat + 0.1 / 110_540.0,
    )
    candidates = fuse_detections((first, second), radius_m=6.0)
    assert len(candidates) == 1
    assert candidates[0].view_count == 2


def test_fusion_rejects_overspread_components() -> None:
    """A diameter cap prevents a long chain from becoming one candidate."""
    base = detection_from_box(_image(), (400.0, 500.0, 600.0, 700.0), score=0.8, depth_m=8.0)
    first = replace(base, lon=base.lon)
    second = replace(base, image_id="image-2", lon=base.lon + 12.0 / 85_000.0)
    candidates = fuse_detections((first, second), radius_m=20.0, max_spread_m=10.0)
    assert len(candidates) == 2


def test_fusion_transitively_links_detection_chain() -> None:
    """Union-find links a chain even when the endpoints are farther than the radius."""
    base = detection_from_box(_image(), (400.0, 500.0, 600.0, 700.0), score=0.8, depth_m=8.0)
    detections = tuple(
        replace(base, image_id=f"image-{index}", lon=base.lon + offset / 85_000.0)
        for index, offset in enumerate((0.0, 4.0, 8.0))
    )
    candidates = fuse_detections(detections, radius_m=6.0)
    assert len(candidates) == 1
    assert candidates[0].view_count == 3


def test_inventory_match_is_descriptive() -> None:
    """Inventory matching counts near public records without claiming completeness."""
    first = detection_from_box(_image(), (400.0, 500.0, 600.0, 700.0), score=0.8, depth_m=8.0)
    second = detection_from_box(
        _image(image_id="image-2", lat=49.3),
        (400.0, 500.0, 600.0, 700.0),
        score=0.8,
        depth_m=8.0,
    )
    candidates = fuse_detections((first, second), radius_m=1.0)
    summary = match_inventory(candidates, ((first.lon, first.lat, "public-1"),), tolerance_m=1.0)
    assert summary.candidate_count == 2
    assert summary.matched_count == 1
    assert summary.median_distance_m == 0.0
    assert summary.tolerance_m == 1.0


def test_kartaview_record_is_parsed_with_assumed_fov() -> None:
    """The public provider normalizes a KartaView record."""
    payload = {
        "result": {
            "data": [
                {
                    "id": "42",
                    "lat": "49.25",
                    "lng": "-123.1",
                    "heading": "90",
                    "width": "1280",
                    "height": "960",
                    "dateAdded": "2020-01-01",
                    "imageLthUrl": "https://example.test/42.jpg",
                    "fieldOfView": "0",
                }
            ]
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["lat"] == "49.25"
        return httpx.Response(200, json=payload)

    client = KartaViewClient(httpx.Client(transport=httpx.MockTransport(handler)))
    images = client.images_near(lon=-123.1, lat=49.25, radius_m=100, limit=10)
    assert len(images) == 1
    assert images[0].fov_source == "assumed"
    assert images[0].horizontal_fov_deg == 60.0
    assert images[0].license == "CC BY-SA 4.0"


def test_geojson_marks_candidates_as_separate_lineage() -> None:
    """Output features remain separate from LiDAR off-inventory candidates."""
    detection = detection_from_box(_image(), (400.0, 500.0, 600.0, 700.0), score=0.8, depth_m=8.0)
    candidates = fuse_detections((detection,))
    geojson = candidates_geojson(candidates)
    features = geojson["features"]
    assert isinstance(features, list)
    feature = features[0]
    assert isinstance(feature, dict)
    properties = feature["properties"]
    assert isinstance(properties, dict)
    assert properties["source"] == "street_level_cv"
    assert properties["not_ground_truth"] is True
    assert "separate from LiDAR off-inventory" in properties["lineage"]


def test_write_candidates_round_trip(tmp_path: Path) -> None:
    """Candidate GeoJSON can be written to a path."""
    detection = detection_from_box(_image(), (400.0, 500.0, 600.0, 700.0), score=0.8, depth_m=8.0)
    candidates = fuse_detections((detection,))
    path = tmp_path / "street.json"
    from fresh_urban_forest.street_trees import write_candidates

    write_candidates(path, candidates)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "fresh-urban-forest.street-tree-candidates.v1"
    assert len(payload["features"]) == 1
