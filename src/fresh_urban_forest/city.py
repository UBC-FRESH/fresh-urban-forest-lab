"""Full-city LiDAR rasterisation and mosaic assembly.

The UBC prototype rasterises a single LAZ file against an existing DEM. A city pilot has
181 classified LAS tiles and no pre-built DEM, so this module rasterises each tile into
its own 1 m grid and then mosaics the tiles into a single city grid.
"""

from __future__ import annotations

import json
import math
import zipfile
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import laspy
import numpy as np
import rasterio
from affine import Affine
from numpy.typing import NDArray
from rasterio.features import rasterize
from scipy.ndimage import distance_transform_edt

GROUND_CLASS = 2
WATER_CLASS = 9
BUILDING_CLASS = 6
VEGETATION_CLASSES: tuple[int, ...] = (3, 4, 5)
SURFACE_EXCLUDED_CLASSES: frozenset[int] = frozenset({7, 8, 9})
NOISE_CLASSES: frozenset[int] = frozenset({7, 8})


@dataclass(frozen=True, slots=True)
class CityTile:
    """One rasterised City of Vancouver LiDAR tile.

    Attributes
    ----------
    tile_id : str
        Stable tile identifier, such as ``481000_5456000``.
    crs : str
        Raster CRS.
    resolution_m : float
        Cell size in metres.
    bounds : tuple of float
        ``(left, bottom, right, top)`` in the raster CRS.
    transform : Affine
        Raster transform.
    dem : numpy.ndarray
        Minimum ground elevation per cell, ``numpy.nan`` where no ground return exists.
    dsm : numpy.ndarray
        Maximum non-noise surface elevation per cell.
    vegetation : numpy.ndarray
        Maximum vegetation elevation per cell.
    building : numpy.ndarray
        Maximum building-class elevation per cell.
    water : numpy.ndarray
        Boolean water mask.
    class_counts : tuple of tuple of int and int
        Point counts by classification code.
    point_count : int
        Total point count.
    """

    tile_id: str
    crs: str
    resolution_m: float
    bounds: tuple[float, float, float, float]
    transform: Affine
    dem: NDArray[np.float32]
    dsm: NDArray[np.float32]
    vegetation: NDArray[np.float32]
    building: NDArray[np.float32]
    water: NDArray[np.bool_]
    class_counts: tuple[tuple[int, int], ...]
    point_count: int


@dataclass(frozen=True, slots=True)
class CityMosaic:
    """A city-scale mosaic written to disk.

    Attributes
    ----------
    out_dir : Path
        Directory holding the raster files.
    crs : str
        Raster CRS.
    resolution_m : float
        Cell size in metres.
    bounds : tuple of float
        ``(left, bottom, right, top)``.
    width : int
        Number of columns.
    height : int
        Number of rows.
    tile_count : int
        Number of rasterised tiles used.
    aoi_area_km2 : float
        AOI area in square kilometres.
    coverage_fraction : float
        Fraction of AOI cells covered by at least one tile.
    chm_p50_m : float
        Median positive canopy height over the AOI.
    chm_p95_m : float
        95th percentile positive canopy height over the AOI.
    """

    out_dir: Path
    crs: str
    resolution_m: float
    bounds: tuple[float, float, float, float]
    width: int
    height: int
    tile_count: int
    aoi_area_km2: float
    coverage_fraction: float
    chm_p50_m: float
    chm_p95_m: float


def rasterize_las_tile(
    path: Path,
    *,
    tile_id: str | None = None,
    resolution_m: float = 1.0,
    chunk_size: int = 2_000_000,
    crs_override: str | None = None,
) -> CityTile:
    """Rasterise one classified LAS or LAZ tile.

    Parameters
    ----------
    path : Path
        LAS/LAZ path.
    tile_id : str or None
        Stable identifier. Defaults to the file stem.
    resolution_m : float
        Cell size in metres.
    chunk_size : int
        Points to read per chunk.
    crs_override : str or None
        CRS to assign when the LAS header carries a generic WKT. The City product is
        documented as EPSG:3157 even though the header may report EPSG:26910.

    Returns
    -------
    CityTile
        Tile rasters. Ground, surface, vegetation, and building arrays are filled with
        ``numpy.nan`` where no relevant return exists.
    """
    if resolution_m <= 0:
        raise ValueError("resolution_m must be positive")
    with laspy.open(path) as reader:
        header = reader.header
        crs = crs_override or str(header.parse_crs() or "")
        minimum_x = float(header.mins[0])
        minimum_y = float(header.mins[1])
        maximum_x = float(header.maxs[0])
        maximum_y = float(header.maxs[1])
        left = math.floor(minimum_x / resolution_m) * resolution_m
        top = math.ceil(maximum_y / resolution_m) * resolution_m
        width = max(1, math.ceil((maximum_x - left) / resolution_m))
        height = max(1, math.ceil((top - minimum_y) / resolution_m))
        dem = np.full((height, width), np.inf, dtype=np.float32)
        dsm = np.full((height, width), -np.inf, dtype=np.float32)
        vegetation = np.full((height, width), -np.inf, dtype=np.float32)
        building = np.full((height, width), -np.inf, dtype=np.float32)
        water = np.zeros((height, width), dtype=bool)
        counts: Counter[int] = Counter()
        point_count = 0
        for points in reader.chunk_iterator(chunk_size):
            x = np.asarray(points.x, dtype=np.float64)
            y = np.asarray(points.y, dtype=np.float64)
            z = np.asarray(points.z, dtype=np.float32)
            classes = np.asarray(points.classification, dtype=np.int16)
            point_count += len(x)
            for code, count in zip(*np.unique(classes, return_counts=True), strict=True):
                counts[int(code)] += int(count)
            rows, cols = _rows_cols(x, y, left, top, resolution_m)
            valid = (rows >= 0) & (rows < height) & (cols >= 0) & (cols < width)
            if not np.any(valid):
                continue
            rows = rows[valid]
            cols = cols[valid]
            z = z[valid]
            classes = classes[valid]
            ground = classes == GROUND_CLASS
            if np.any(ground):
                np.minimum.at(dem, (rows[ground], cols[ground]), z[ground])
            surface = ~np.isin(classes, list(SURFACE_EXCLUDED_CLASSES))
            if np.any(surface):
                np.maximum.at(dsm, (rows[surface], cols[surface]), z[surface])
            veg = np.isin(classes, VEGETATION_CLASSES)
            if np.any(veg):
                np.maximum.at(vegetation, (rows[veg], cols[veg]), z[veg])
            built = classes == BUILDING_CLASS
            if np.any(built):
                np.maximum.at(building, (rows[built], cols[built]), z[built])
            moist = classes == WATER_CLASS
            if np.any(moist):
                water[rows[moist], cols[moist]] = True
    bottom = top - height * resolution_m
    right = left + width * resolution_m
    return CityTile(
        tile_id=tile_id or path.stem,
        crs=crs,
        resolution_m=resolution_m,
        bounds=(left, bottom, right, top),
        transform=Affine(resolution_m, 0.0, left, 0.0, -resolution_m, top),
        dem=_finite_or_nan(dem),
        dsm=_finite_or_nan(dsm),
        vegetation=_finite_or_nan(vegetation),
        building=_finite_or_nan(building),
        water=water,
        class_counts=tuple(sorted(counts.items())),
        point_count=point_count,
    )


def rasterize_zip_tile(
    zip_path: Path,
    *,
    scratch_dir: Path,
    resolution_m: float = 1.0,
    crs_override: str | None = None,
) -> CityTile:
    """Extract and rasterise the LAS member of a City tile ZIP.

    Parameters
    ----------
    zip_path : Path
        City ZIP containing one LAS and optional sidecars.
    scratch_dir : Path
        Directory used for the temporary LAS extraction.
    resolution_m : float
        Cell size in metres.
    crs_override : str or None
        CRS assigned to the tile; the City product is documented as EPSG:3157.

    Returns
    -------
    CityTile
        Rasterised tile.

    Raises
    ------
    FileNotFoundError
        When the ZIP contains no LAS/LAZ member.
    """
    scratch_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith((".las", ".laz"))]
        if not members:
            raise FileNotFoundError(f"no LAS/LAZ member in {zip_path}")
        member = members[0]
        extracted = scratch_dir / Path(member).name
        if not extracted.exists() or extracted.stat().st_size == 0:
            archive.extract(member, scratch_dir)
        return rasterize_las_tile(
            extracted,
            tile_id=zip_path.stem,
            resolution_m=resolution_m,
            crs_override=crs_override,
        )


def save_city_tile(tile: CityTile, path: Path) -> Path:
    """Write one rasterised tile as a compressed NPZ.

    Parameters
    ----------
    tile : CityTile
        Tile to write.
    path : Path
        Destination path.

    Returns
    -------
    Path
        The written path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        dem=tile.dem,
        dsm=tile.dsm,
        vegetation=tile.vegetation,
        building=tile.building,
        water=tile.water.astype(np.uint8),
        bounds=np.asarray(tile.bounds, dtype=np.float64),
        transform=np.asarray(tuple(tile.transform)[:6], dtype=np.float64),
        crs=np.asarray(tile.crs),
        resolution=np.asarray(tile.resolution_m),
        class_counts=np.asarray(tile.class_counts, dtype=np.int64),
        point_count=np.asarray(tile.point_count, dtype=np.int64),
    )
    return path


def load_city_tile(path: Path) -> CityTile:
    """Read one rasterised tile from an NPZ.

    Parameters
    ----------
    path : Path
        NPZ path.

    Returns
    -------
    CityTile
        Loaded tile.
    """
    with np.load(path, allow_pickle=False) as archive:
        dem = np.asarray(archive["dem"], dtype=np.float32)
        dsm = np.asarray(archive["dsm"], dtype=np.float32)
        vegetation = np.asarray(archive["vegetation"], dtype=np.float32)
        building = np.asarray(archive["building"], dtype=np.float32)
        water = np.asarray(archive["water"], dtype=bool)
        bounds = tuple(float(value) for value in archive["bounds"].tolist())
        six = tuple(float(value) for value in archive["transform"].tolist())
        crs = str(archive["crs"].item())
        resolution = float(archive["resolution"].item())
        counts = tuple(
            (int(row[0]), int(row[1])) for row in np.asarray(archive["class_counts"]).tolist()
        )
        point_count = int(archive["point_count"].item())
    return CityTile(
        tile_id=path.stem,
        crs=crs,
        resolution_m=resolution,
        bounds=(bounds[0], bounds[1], bounds[2], bounds[3]),
        transform=Affine(*six[:6]),
        dem=dem,
        dsm=dsm,
        vegetation=vegetation,
        building=building,
        water=water,
        class_counts=counts,
        point_count=point_count,
    )


def build_city_mosaic(
    tile_paths: list[Path],
    *,
    aoi_path: Path,
    out_dir: Path,
    resolution_m: float = 1.0,
    aoi_crs: str | None = None,
) -> CityMosaic:
    """Mosaic rasterised tiles and clip them to an AOI polygon.

    Parameters
    ----------
    tile_paths : list of Path
        Rasterised tile NPZ paths.
    aoi_path : Path
        GeoJSON polygon or multipolygon in any CRS.
    out_dir : Path
        Directory for the output rasters and manifest.
    resolution_m : float
        Cell size in metres.
    aoi_crs : str or None
        CRS to assign when the AOI file has no CRS metadata.

    Returns
    -------
    CityMosaic
        Summary of the written mosaic.

    Raises
    ------
    ValueError
        When no tiles are supplied or their CRSs differ.
    """
    if not tile_paths:
        raise ValueError("no tiles supplied")
    import geopandas as gpd

    aoi = gpd.read_file(aoi_path)
    if aoi_crs is not None:
        aoi = aoi.set_crs(aoi_crs, allow_override=True)
    tiles = [load_city_tile(path) for path in tile_paths]
    crs = tiles[0].crs
    if any(tile.crs != crs for tile in tiles):
        raise ValueError("tiles have mixed CRS")
    aoi = aoi.to_crs(crs)
    min_x, min_y, max_x, max_y = (float(value) for value in aoi.total_bounds)
    left = math.floor(min_x / resolution_m) * resolution_m
    top = math.ceil(max_y / resolution_m) * resolution_m
    width = max(1, math.ceil((max_x - left) / resolution_m))
    height = max(1, math.ceil((top - min_y) / resolution_m))
    if width * height > 1_000_000_000:
        raise ValueError("AOI and tile CRS do not overlap at a plausible city scale")
    dem = np.full((height, width), np.inf, dtype=np.float32)
    dsm = np.full((height, width), -np.inf, dtype=np.float32)
    vegetation = np.full((height, width), -np.inf, dtype=np.float32)
    building = np.full((height, width), -np.inf, dtype=np.float32)
    water = np.zeros((height, width), dtype=bool)
    coverage = np.zeros((height, width), dtype=bool)
    for tile in tiles:
        row0, col0, row1, col1, tile_row0, tile_col0 = _overlap_window(
            tile.bounds, left, top, height, width, resolution_m
        )
        if row0 >= row1 or col0 >= col1:
            continue
        src_dem = tile.dem[
            tile_row0 : tile_row0 + (row1 - row0),
            tile_col0 : tile_col0 + (col1 - col0),
        ]
        src_dsm = tile.dsm[
            tile_row0 : tile_row0 + (row1 - row0),
            tile_col0 : tile_col0 + (col1 - col0),
        ]
        src_veg = tile.vegetation[
            tile_row0 : tile_row0 + (row1 - row0), tile_col0 : tile_col0 + (col1 - col0)
        ]
        src_building = tile.building[
            tile_row0 : tile_row0 + (row1 - row0), tile_col0 : tile_col0 + (col1 - col0)
        ]
        src_water = tile.water[
            tile_row0 : tile_row0 + (row1 - row0), tile_col0 : tile_col0 + (col1 - col0)
        ]
        dem[row0:row1, col0:col1] = np.fmin(dem[row0:row1, col0:col1], src_dem)
        dsm[row0:row1, col0:col1] = np.fmax(dsm[row0:row1, col0:col1], src_dsm)
        vegetation[row0:row1, col0:col1] = np.fmax(vegetation[row0:row1, col0:col1], src_veg)
        building[row0:row1, col0:col1] = np.fmax(building[row0:row1, col0:col1], src_building)
        water[row0:row1, col0:col1] |= src_water
        coverage[row0:row1, col0:col1] = True
    aoi_mask = rasterize(
        [geom.__geo_interface__ for geom in aoi.geometry],
        out_shape=(height, width),
        transform=Affine(resolution_m, 0.0, left, 0.0, -resolution_m, top),
        fill=0,
        default_value=1,
        dtype=np.uint8,
    ).astype(bool)
    dem = _finite_or_nan(dem)
    dsm = _finite_or_nan(dsm)
    vegetation = _finite_or_nan(vegetation)
    building = _finite_or_nan(building)
    dem_filled = _fill_dem(dem)
    valid = coverage & aoi_mask
    canopy = np.where(valid, np.maximum(0.0, vegetation - dem_filled), np.nan).astype(np.float32)
    canopy = np.where(np.isfinite(canopy), canopy, np.nan).astype(np.float32)
    building_height = np.where(
        valid & np.isfinite(building), np.maximum(0.0, building - dem_filled), np.nan
    ).astype(np.float32)
    building_mask = (valid & np.isfinite(building)).astype(np.uint8)
    water_mask = (valid & water).astype(np.uint8)
    coverage_mask = valid.astype(np.uint8)
    out_dir.mkdir(parents=True, exist_ok=True)
    transform = Affine(resolution_m, 0.0, left, 0.0, -resolution_m, top)
    _write_raster(out_dir / "dem.tif", dem_filled, crs, transform, np.nan)
    _write_raster(out_dir / "dsm.tif", dsm, crs, transform, np.nan)
    _write_raster(out_dir / "chm.tif", canopy, crs, transform, np.nan)
    _write_raster(out_dir / "building_height.tif", building_height, crs, transform, np.nan)
    _write_mask(out_dir / "building_mask.tif", building_mask, crs, transform)
    _write_mask(out_dir / "water_mask.tif", water_mask, crs, transform)
    _write_mask(out_dir / "coverage_mask.tif", coverage_mask, crs, transform)
    _write_mask(out_dir / "aoi_mask.tif", aoi_mask.astype(np.uint8), crs, transform)
    positive = canopy[np.isfinite(canopy) & (canopy > 0.0)]
    coverage_fraction = float(
        int(np.count_nonzero(valid)) / max(1, int(np.count_nonzero(aoi_mask)))
    )
    summary = CityMosaic(
        out_dir=out_dir,
        crs=crs,
        resolution_m=resolution_m,
        bounds=(left, top - height * resolution_m, left + width * resolution_m, top),
        width=width,
        height=height,
        tile_count=len(tiles),
        aoi_area_km2=float(aoi.geometry.area.sum() / 1e6),
        coverage_fraction=coverage_fraction,
        chm_p50_m=float(np.percentile(positive, 50)) if positive.size else 0.0,
        chm_p95_m=float(np.percentile(positive, 95)) if positive.size else 0.0,
    )
    class_counts: Counter[int] = Counter()
    point_count = 0
    for tile in tiles:
        point_count += tile.point_count
        class_counts.update(dict(tile.class_counts))
    manifest = {
        "schema_version": "fresh-urban-forest.city-mosaic.v1",
        "tile_count": summary.tile_count,
        "point_count": point_count,
        "class_counts": {str(key): value for key, value in sorted(class_counts.items())},
        "crs": crs,
        "resolution_m": resolution_m,
        "bounds": list(summary.bounds),
        "width": width,
        "height": height,
        "aoi_area_km2": summary.aoi_area_km2,
        "coverage_fraction": summary.coverage_fraction,
        "chm_p50_m": summary.chm_p50_m,
        "chm_p95_m": summary.chm_p95_m,
        "files": {
            "dem": "dem.tif",
            "dsm": "dsm.tif",
            "chm": "chm.tif",
            "building_height": "building_height.tif",
            "building_mask": "building_mask.tif",
            "water_mask": "water_mask.tif",
            "coverage_mask": "coverage_mask.tif",
            "aoi_mask": "aoi_mask.tif",
        },
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return summary


def _rows_cols(
    x: NDArray[np.float64],
    y: NDArray[np.float64],
    left: float,
    top: float,
    resolution_m: float,
) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    """Convert projected coordinates to integer rows and columns."""
    rows = np.floor((top - y) / resolution_m).astype(np.int64)
    cols = np.floor((x - left) / resolution_m).astype(np.int64)
    return rows, cols


def _finite_or_nan(array: NDArray[np.float32]) -> NDArray[np.float32]:
    """Replace positive or negative infinity with NaN."""
    result = np.asarray(array, dtype=np.float32).copy()
    result[~np.isfinite(result)] = np.nan
    return result


def _overlap_window(
    tile_bounds: tuple[float, float, float, float],
    left: float,
    top: float,
    height: int,
    width: int,
    resolution_m: float,
) -> tuple[int, int, int, int, int, int]:
    """Return the destination window and source offsets for one tile."""
    col0 = round((tile_bounds[0] - left) / resolution_m)
    row0 = round((top - tile_bounds[3]) / resolution_m)
    col1 = col0 + round((tile_bounds[2] - tile_bounds[0]) / resolution_m)
    row1 = row0 + round((tile_bounds[3] - tile_bounds[1]) / resolution_m)
    src_col0 = max(0, -col0)
    src_row0 = max(0, -row0)
    col0 = max(0, col0)
    row0 = max(0, row0)
    col1 = min(width, col1)
    row1 = min(height, row1)
    return row0, col0, row1, col1, src_row0, src_col0


def _fill_dem(dem: NDArray[np.float32]) -> NDArray[np.float32]:
    """Fill DEM gaps with the nearest valid ground elevation."""
    if not np.any(~np.isfinite(dem)):
        return dem
    if not np.any(np.isfinite(dem)):
        return np.zeros_like(dem, dtype=np.float32)
    indices = distance_transform_edt(~np.isfinite(dem), return_distances=False, return_indices=True)
    return np.asarray(dem[tuple(indices)], dtype=np.float32)


def _write_raster(
    path: Path,
    array: NDArray[np.float32],
    crs: str,
    transform: Affine,
    nodata: float,
) -> None:
    """Write a single-band float32 GeoTIFF."""
    profile: Mapping[str, object] = {
        "driver": "GTiff",
        "height": int(array.shape[0]),
        "width": int(array.shape[1]),
        "count": 1,
        "dtype": "float32",
        "crs": crs,
        "transform": transform,
        "nodata": nodata,
        "compress": "deflate",
        "tiled": True,
        "blockxsize": 512,
        "blockysize": 512,
    }
    with rasterio.open(path, "w", **profile) as dataset:
        dataset.write(array.astype(np.float32), 1)


def _write_mask(path: Path, array: NDArray[np.uint8], crs: str, transform: Affine) -> None:
    """Write a single-band uint8 mask GeoTIFF."""
    profile: Mapping[str, object] = {
        "driver": "GTiff",
        "height": int(array.shape[0]),
        "width": int(array.shape[1]),
        "count": 1,
        "dtype": "uint8",
        "crs": crs,
        "transform": transform,
        "nodata": 255,
        "compress": "deflate",
        "tiled": True,
        "blockxsize": 512,
        "blockysize": 512,
    }
    with rasterio.open(path, "w", **profile) as dataset:
        dataset.write(array.astype(np.uint8), 1)
