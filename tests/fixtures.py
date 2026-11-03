"""Small synthetic datasets shared by the test suite."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from rasterio.transform import from_origin

from fresh_urban_forest.dataset import build_dataset
from fresh_urban_forest.models import Building, TreeRecord, UrbanForestDataset
from fresh_urban_forest.terrain import RasterData

CRS = "EPSG:3157"
BOUNDS = (0.0, 0.0, 100.0, 100.0)
GENERATED = "2026-11-03T00:00:00Z"


def make_raster(
    path: Path,
    values: np.ndarray,
    *,
    bounds: tuple[float, float, float, float] = BOUNDS,
) -> RasterData:
    """Build an in-memory raster with an affine transform.

    Parameters
    ----------
    path : Path
        Nominal source path.
    values : numpy.ndarray
        Raster values.
    bounds : tuple of float
        ``(left, bottom, right, top)``.

    Returns
    -------
    RasterData
        Raster data.
    """
    rows, cols = values.shape
    transform = from_origin(
        bounds[0],
        bounds[3],
        (bounds[2] - bounds[0]) / cols,
        (bounds[3] - bounds[1]) / rows,
    )
    return RasterData(
        path=path,
        crs=CRS,
        transform=transform,
        bounds=bounds,
        array=np.asarray(values, dtype=np.float32),
        cell_area_m2=(bounds[2] - bounds[0]) * (bounds[3] - bounds[1]) / (rows * cols),
    )


def make_trees(count: int = 12) -> list[TreeRecord]:
    """Build a small tree population.

    Parameters
    ----------
    count : int
        Number of trees.

    Returns
    -------
    list of TreeRecord
        Trees spread across the synthetic grid.
    """
    trees: list[TreeRecord] = []
    for index in range(count):
        x = 10.0 + (index % 4) * 20.0
        y = 10.0 + (index // 4) * 20.0
        lon, lat = _unproject(x, y)
        species = "Thuja plicata" if index % 3 == 0 else "Acer rubrum"
        trees.append(
            TreeRecord(
                tree_id=f"test:{index + 1}",
                lon=lon,
                lat=lat,
                species=species,
                common_name="Western red cedar" if index % 3 == 0 else "Red maple",
                genus=species.split()[0],
                dbh_cm=12.0 + index,
                height_m=8.0 + index * 0.4,
                crown_width_m=3.0 + index * 0.1,
                crown_ratio=0.55,
                source="test",
                native=index % 3 == 0,
                x_m=x,
                y_m=y,
                elevation_m=0.0,
                attributes={"crown_light_exposure": str(index % 6)},
            )
        )
    trees[0] = TreeRecord(
        tree_id="test:1",
        lon=trees[0].lon,
        lat=trees[0].lat,
        species=trees[0].species,
        common_name=trees[0].common_name,
        genus=trees[0].genus,
        dbh_cm=None,
        height_m=None,
        crown_width_m=None,
        crown_ratio=0.55,
        source="test",
        native=True,
        x_m=trees[0].x_m,
        y_m=trees[0].y_m,
        elevation_m=0.0,
        attributes={},
    )
    return trees


def make_dataset(tmp_path: Path) -> UrbanForestDataset:
    """Build and write a synthetic dataset.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory.

    Returns
    -------
    UrbanForestDataset
        The written dataset.
    """
    rows = cols = 20
    dem_values = np.zeros((rows, cols), dtype=np.float32)
    chm_values = np.zeros((rows, cols), dtype=np.float32)
    chm_values[:, 8:] = 12.0
    chm_values[4:8, 2:6] = 6.0
    dem = make_raster(tmp_path / "dem.tif", dem_values)
    chm = make_raster(tmp_path / "chm.tif", chm_values)
    buildings = [
        Building(
            building_id="b1",
            name="Test building",
            height_m=12.0,
            rings=(
                (
                    (_lon(25), _lat(25)),
                    (_lon(35), _lat(25)),
                    (_lon(35), _lat(35)),
                    (_lon(25), _lat(35)),
                ),
            ),
        )
    ]
    boundary = (
        (_lon(0), _lat(0)),
        (_lon(100), _lat(0)),
        (_lon(100), _lat(100)),
        (_lon(0), _lat(100)),
        (_lon(0), _lat(0)),
    )
    return build_dataset(
        name="Test urban forest",
        trees=make_trees(),
        dem=dem,
        chm=chm,
        out_dir=tmp_path / "dataset",
        buildings=buildings,
        boundary=boundary,
        generated_utc=GENERATED,
    )


def _unproject(x: float, y: float) -> tuple[float, float]:
    """Convert a synthetic local point to WGS84.

    Parameters
    ----------
    x : float
        Easting.
    y : float
        Northing.

    Returns
    -------
    tuple of float
        Longitude and latitude.
    """
    from pyproj import Transformer

    transformer = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True)
    lon, lat = transformer.transform(x, y)
    return (float(lon), float(lat))


def _lon(x: float) -> float:
    """Convert a local easting to longitude.

    Parameters
    ----------
    x : float
        Easting.

    Returns
    -------
    float
        Longitude.
    """
    return _unproject(x, 50.0)[0]


def _lat(y: float) -> float:
    """Convert a local northing to latitude.

    Parameters
    ----------
    y : float
        Northing.

    Returns
    -------
    float
        Latitude.
    """
    return _unproject(50.0, y)[1]


__all__ = ["BOUNDS", "CRS", "GENERATED", "make_dataset", "make_raster", "make_trees"]
