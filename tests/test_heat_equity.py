"""Tests for the Landsat LST and heat-equity screen."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from fresh_urban_forest.heat_equity import (
    HEAT_EQUITY_EVIDENCE,
    LST_SCALE,
    LSTScene,
    build_heat_equity_grid,
    composite_lst,
    heat_equity_geojson,
    heat_equity_png,
    read_landsat_lst,
    write_heat_equity_product,
)

CRS = "EPSG:3157"
BOUNDS = (493_000.0, 5_455_000.0, 493_300.0, 5_455_300.0)


def _write_scene(
    tmp_path: Path,
    name: str,
    values: np.ndarray,
    qa: np.ndarray,
) -> tuple[Path, Path]:
    """Write a tiny Landsat ST_B10 and QA_PIXEL pair."""
    directory = tmp_path / name
    directory.mkdir()
    st_path = directory / "ST_B10.TIF"
    qa_path = directory / "QA_PIXEL.TIF"
    for path, array, dtype in ((st_path, values, "uint16"), (qa_path, qa, "uint16")):
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=array.shape[0],
            width=array.shape[1],
            count=1,
            dtype=dtype,
            crs=CRS,
            transform=from_origin(BOUNDS[0], BOUNDS[3], 30.0, 30.0),
            nodata=0,
        ) as dataset:
            dataset.write(array.astype(dtype), 1)
    return st_path, qa_path


def _scene_values(value: int = 42000) -> np.ndarray:
    """Return a 10 by 10 digital-number scene."""
    return np.full((10, 10), value, dtype=np.uint16)


def _clear_qa() -> np.ndarray:
    """Return a clear QA scene."""
    return np.full((10, 10), 1 << 6, dtype=np.uint16)


def test_read_landsat_lst_masks_clouds_water_and_exclusion(tmp_path: Path) -> None:
    """The reader applies the ST scale/offset and the QA and exclusion masks."""
    values = _scene_values()
    qa = _clear_qa()
    qa[2, 2] |= 1 << 3
    qa[3, 3] |= 1 << 7
    st_path, qa_path = _write_scene(tmp_path, "scene", values, qa)
    exclusion = np.zeros((10, 10), dtype=np.bool_)
    exclusion[8, 8] = True
    scene = read_landsat_lst(
        st_path,
        qa_path,
        bounds=BOUNDS,
        crs=CRS,
        resolution_m=30.0,
        exclusion_mask=exclusion,
    )
    expected = 42000 * LST_SCALE + 149.0 - 273.15
    assert scene.shape == (10, 10)
    assert scene.valid[0, 0]
    assert not scene.valid[2, 2]
    assert not scene.valid[3, 3]
    assert not scene.valid[8, 8]
    assert float(scene.lst_c[0, 0]) == pytest.approx(expected, abs=0.01)
    assert scene.scene_id == "scene"


def test_read_landsat_lst_rejects_bad_inputs(tmp_path: Path) -> None:
    """Invalid bounds, resolution, exclusion shape, and all-invalid scenes fail."""
    st_path, qa_path = _write_scene(tmp_path, "scene", _scene_values(), _clear_qa())
    with pytest.raises(ValueError, match="positive width"):
        read_landsat_lst(st_path, qa_path, bounds=(0.0, 0.0, 0.0, 1.0), crs=CRS)
    with pytest.raises(ValueError, match="resolution_m"):
        read_landsat_lst(st_path, qa_path, bounds=BOUNDS, crs=CRS, resolution_m=0.0)
    with pytest.raises(ValueError, match="exclusion_mask"):
        read_landsat_lst(
            st_path,
            qa_path,
            bounds=BOUNDS,
            crs=CRS,
            exclusion_mask=np.zeros((9, 9), dtype=np.bool_),
        )
    cloud = np.full((10, 10), 0, dtype=np.uint16)
    cloud[:] = 1 << 3
    cloud_path, cloud_qa = _write_scene(tmp_path, "cloud", _scene_values(), cloud)
    with pytest.raises(ValueError, match="no usable LST"):
        read_landsat_lst(cloud_path, cloud_qa, bounds=BOUNDS, crs=CRS)


def _scene(value: int, scene_id: str) -> LSTScene:
    """Build an in-memory scene for composite tests."""
    return LSTScene(
        scene_id=scene_id,
        lst_c=np.full((10, 10), float(value), dtype=np.float32),
        valid=np.ones((10, 10), dtype=np.bool_),
        bounds=BOUNDS,
        shape=(10, 10),
        transform=from_origin(BOUNDS[0], BOUNDS[3], 30.0, 30.0),
        evidence=HEAT_EQUITY_EVIDENCE,
    )


def test_composite_lst_takes_pixelwise_median() -> None:
    """The composite is the median across valid scenes."""
    composite = composite_lst((_scene(10, "a"), _scene(20, "b"), _scene(30, "c")))
    assert float(composite.lst_c[0, 0]) == pytest.approx(20.0)
    assert int(composite.valid_count[0, 0]) == 3
    assert len(composite.scenes) == 3
    assert composite.to_dict()["valid_pixels"] == 100


def test_composite_lst_rejects_empty_and_mismatched() -> None:
    """Empty and mismatched scene sets are rejected."""
    with pytest.raises(ValueError, match="at least one"):
        composite_lst(())
    bad = _scene(10, "bad")
    bad = LSTScene(
        scene_id="bad",
        lst_c=bad.lst_c,
        valid=bad.valid,
        bounds=(0.0, 0.0, 1.0, 1.0),
        shape=(10, 10),
        transform=bad.transform,
        evidence=bad.evidence,
    )
    with pytest.raises(ValueError, match="share a grid"):
        composite_lst((_scene(10, "a"), bad))


def test_build_heat_equity_grid_uses_five_part_index() -> None:
    """LST and the P38 social score combine with four-fifths social weight."""
    composite = composite_lst((_scene(30, "a"),))
    priority = {
        "r00c00": {
            "equity_score": 0.8,
            "shade_deficit": 0.7,
            "priority_class": "1A",
        }
    }
    cells = build_heat_equity_grid(
        composite,
        crs=CRS,
        priority=priority,
        cell_size_m=400.0,
    )
    assert len(cells) == 1
    cell = cells[0]
    assert cell.lst_mean_c == pytest.approx(30.0)
    assert cell.lst_p90_c == pytest.approx(30.0)
    assert cell.social_equity_score == pytest.approx(0.8)
    assert cell.shade_deficit == pytest.approx(0.7)
    assert cell.priority_class == "1A"
    assert 0.0 <= cell.tespi_like <= 1.0
    assert cell.heat_equity_tier in {"high", "medium", "low"}


def test_heat_equity_exports(tmp_path: Path) -> None:
    """GeoJSON is WGS84 and the PNG and product files are written."""
    composite = composite_lst((_scene(30, "a"),))
    cells = build_heat_equity_grid(
        composite,
        crs=CRS,
        priority={"r00c00": {"equity_score": 0.8, "shade_deficit": 0.7}},
        cell_size_m=400.0,
    )
    collection = heat_equity_geojson(cells, crs=CRS, metadata={"method": "test"})
    features = cast("list[dict[str, object]]", collection["features"])
    geometry = cast("dict[str, object]", features[0]["geometry"])
    coordinates = cast("list[list[list[float]]]", geometry["coordinates"])[0][0]
    assert -180.0 <= coordinates[0] <= 180.0
    assert -90.0 <= coordinates[1] <= 90.0
    assert heat_equity_png(cells).startswith(b"\x89PNG")
    paths = write_heat_equity_product(
        cells,
        tmp_path,
        crs=CRS,
        metadata={"method": "test", "evidence": HEAT_EQUITY_EVIDENCE.to_dict()},
    )
    assert paths["json"].exists()
    assert paths["geojson"].exists()
    assert paths["png"].exists()
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == "fresh-urban-forest.heat-equity.v1"
    assert len(payload["cells"]) == 1


def test_build_heat_equity_grid_rejects_bad_cell_size() -> None:
    """A non-positive cell size is rejected."""
    composite = composite_lst((_scene(30, "a"),))
    with pytest.raises(ValueError, match="cell_size_m"):
        build_heat_equity_grid(composite, crs=CRS, cell_size_m=0.0)
