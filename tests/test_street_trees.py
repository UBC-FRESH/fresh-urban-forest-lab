"""Tests for the street-level tree candidate geometry and provider."""

from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from fresh_urban_forest.street_trees import (
    KartaViewClient,
    StreetImage,
    _parse_kartaview_record,
    bearing_offset_deg,
    candidates_geojson,
    detection_from_box,
    fuse_detections,
    match_inventory,
    project_pixel,
    write_candidates,
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


def test_projection_rejects_invalid_inputs() -> None:
    """Projection helpers reject impossible dimensions and depths."""
    with pytest.raises(ValueError, match="width must be positive"):
        bearing_offset_deg(0.0, 0, 60.0)
    with pytest.raises(ValueError, match="horizontal_fov_deg"):
        bearing_offset_deg(0.0, 1000, 0.0)
    with pytest.raises(ValueError, match="depth_m"):
        project_pixel(_image(), 500.0, 0.0)


def test_fusion_rejects_invalid_options() -> None:
    """Fusion validates its radius, spread, and empty input."""
    assert fuse_detections(()) == ()
    detection = detection_from_box(_image(), (400.0, 500.0, 600.0, 700.0), score=0.8, depth_m=8.0)
    with pytest.raises(ValueError, match="radius_m"):
        fuse_detections((detection,), radius_m=0.0)
    with pytest.raises(ValueError, match="max_spread_m"):
        fuse_detections((detection,), radius_m=1.0, max_spread_m=0.0)


def test_fusion_handles_a_closed_triangle() -> None:
    """Repeated edges and a closed triangle do not duplicate candidates."""
    base = detection_from_box(_image(), (400.0, 500.0, 600.0, 700.0), score=0.8, depth_m=8.0)
    points = (
        replace(base, image_id="image-a", lon=base.lon, lat=base.lat),
        replace(base, image_id="image-b", lon=base.lon + 4.0 / 85_000.0, lat=base.lat),
        replace(
            base,
            image_id="image-c",
            lon=base.lon,
            lat=base.lat + 4.0 / 110_540.0,
        ),
    )
    candidates = fuse_detections(points, radius_m=6.0, max_spread_m=10.0)
    assert len(candidates) == 1
    assert candidates[0].view_count == 3


def test_inventory_match_rejects_invalid_tolerance_and_empty_inputs() -> None:
    """Inventory matching validates tolerance and handles empty inputs."""
    detection = detection_from_box(_image(), (400.0, 500.0, 600.0, 700.0), score=0.8, depth_m=8.0)
    candidates = fuse_detections((detection,))
    with pytest.raises(ValueError, match="tolerance_m"):
        match_inventory(candidates, ((detection.lon, detection.lat, "public-1"),), tolerance_m=0.0)
    empty = match_inventory((), ((detection.lon, detection.lat, "public-1"),), tolerance_m=8.0)
    assert empty.matched_count == 0
    no_inventory = match_inventory(candidates, (), tolerance_m=8.0)
    assert no_inventory.matched_count == 0


def test_inventory_match_handles_no_nearby_records() -> None:
    """A candidate outside the tolerance has no matched distance."""
    detection = detection_from_box(_image(), (400.0, 500.0, 600.0, 700.0), score=0.8, depth_m=8.0)
    candidates = fuse_detections((detection,))
    summary = match_inventory(
        candidates,
        ((detection.lon + 0.1, detection.lat + 0.1, "public-far"),),
        tolerance_m=8.0,
    )
    assert summary.matched_count == 0
    assert summary.median_distance_m is None


def test_kartaview_client_rejects_invalid_query_limits() -> None:
    """The provider validates radius and limit before making a request."""
    transport = httpx.MockTransport(lambda request: httpx.Response(500))
    client = KartaViewClient(httpx.Client(transport=transport))
    with pytest.raises(ValueError, match="radius_m and limit"):
        client.images_near(lon=-123.1, lat=49.25, radius_m=0, limit=10)
    with pytest.raises(ValueError, match="radius_m and limit"):
        client.images_near(lon=-123.1, lat=49.25, radius_m=100, limit=0)


def test_kartaview_client_handles_malformed_payloads() -> None:
    """Malformed provider payloads are rejected or treated as empty."""

    def list_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    with pytest.raises(ValueError, match="not an object"):
        KartaViewClient(httpx.Client(transport=httpx.MockTransport(list_handler))).images_near(
            lon=-123.1, lat=49.25, radius_m=100, limit=10
        )

    payloads: tuple[dict[str, object], ...] = (
        {"result": []},
        {"result": {"data": {}}},
        {"result": {"data": [1, {}]}},
    )
    for payload in payloads:

        def handler(request: httpx.Request, payload: object = payload) -> httpx.Response:
            return httpx.Response(200, json=payload)

        client = KartaViewClient(httpx.Client(transport=httpx.MockTransport(handler)))
        assert client.images_near(lon=-123.1, lat=49.25, radius_m=100, limit=10) == ()


def test_kartaview_client_skips_records_that_fail_parsing() -> None:
    """A malformed record is skipped without aborting the whole response."""
    payload = {
        "result": {
            "data": [
                {
                    "id": "bad",
                    "imageLthUrl": "https://example.test/bad.jpg",
                    "lat": 49.25,
                    "lng": -123.1,
                }
            ]
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = KartaViewClient(httpx.Client(transport=httpx.MockTransport(handler)))
    assert client.images_near(lon=-123.1, lat=49.25, radius_m=100, limit=10) == ()


def test_kartaview_record_parser_rejects_bad_records() -> None:
    """Records without a secure URL, id, or required coordinates are skipped."""
    assert _parse_kartaview_record({"id": "1", "imageLthUrl": "http://example.test/1.jpg"}) is None
    assert _parse_kartaview_record({"id": {}, "imageLthUrl": "https://example.test/1.jpg"}) is None
    parsed = _parse_kartaview_record(
        {
            "id": 7,
            "imageLthUrl": "https://example.test/7.jpg",
            "lat": 49.25,
            "lng": -123.1,
            "heading": 0,
            "width": None,
            "height": None,
        }
    )
    assert parsed is not None
    assert parsed.image_id == "7"
    assert parsed.width == 1280
    assert parsed.height == 960
    with pytest.raises(ValueError, match="missing heading"):
        _parse_kartaview_record(
            {
                "id": "8",
                "imageLthUrl": "https://example.test/8.jpg",
                "lat": 49.25,
                "lng": -123.1,
            }
        )


def test_kartaview_image_bytes_and_write_candidates(tmp_path: Path) -> None:
    """Image bytes are returned and candidate files are written."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"image-bytes")

    client = KartaViewClient(httpx.Client(transport=httpx.MockTransport(handler)))
    assert client.image_bytes(_image()) == b"image-bytes"
    detection = detection_from_box(_image(), (400.0, 500.0, 600.0, 700.0), score=0.8, depth_m=8.0)
    candidates = fuse_detections((detection,))
    path = tmp_path / "candidates.geojson"
    write_candidates(path, candidates)
    assert path.is_file()
