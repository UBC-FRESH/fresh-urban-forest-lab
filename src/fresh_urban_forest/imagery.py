"""Public orthophoto tile access and chip extraction.

The City of Vancouver 2022 orthophoto is published as an ArcGIS tiled map service. This
module keeps the tile cache and chip geometry explicit so training and inference use the
same pixel frame. It does not treat orthophotos as stereo imagery.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
from numpy.typing import NDArray
from PIL import Image

USER_AGENT = "FRESH-Urban-Forest-Lab/0.3 imagery fetch"


@dataclass(frozen=True, slots=True)
class TileSource:
    """An ArcGIS Web Mercator tile source.

    Attributes
    ----------
    name : str
        Source identifier.
    service_url : str
        MapServer service URL.
    zoom : int
        Tile zoom level.
    cache_dir : Path
        Local tile cache.
    """

    name: str
    service_url: str
    zoom: int
    cache_dir: Path

    def tile_bounds(self, lon: float, lat: float) -> tuple[int, int]:
        """Return the Web Mercator tile containing a WGS84 point.

        Parameters
        ----------
        lon, lat : float
            WGS84 coordinates.

        Returns
        -------
        tuple of int
            Tile ``(x, y)``.
        """
        n = 2**self.zoom
        x = (lon + 180.0) / 360.0 * n
        lat_rad = math.radians(max(min(lat, 85.05112878), -85.05112878))
        y = (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n
        return math.floor(x), math.floor(y)

    def global_pixel(self, lon: float, lat: float) -> tuple[float, float]:
        """Return global pixel coordinates at the source zoom.

        Parameters
        ----------
        lon, lat : float
            WGS84 coordinates.

        Returns
        -------
        tuple of float
            Global pixel x and y.
        """
        n = 2**self.zoom * 256
        x = (lon + 180.0) / 360.0 * n
        lat_rad = math.radians(max(min(lat, 85.05112878), -85.05112878))
        y = (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n
        return x, y

    def tile_url(self, x: int, y: int) -> str:
        """Return the URL for one tile.

        Parameters
        ----------
        x, y : int
            Tile coordinates.

        Returns
        -------
        str
            Tile URL.
        """
        return f"{self.service_url.rstrip('/')}/tile/{self.zoom}/{y}/{x}"

    def tile_path(self, x: int, y: int) -> Path:
        """Return the cached tile path.

        Parameters
        ----------
        x, y : int
            Tile coordinates.

        Returns
        -------
        Path
            Cache path.
        """
        return self.cache_dir / str(self.zoom) / str(x) / f"{y}.jpg"

    def tile(self, x: int, y: int) -> Image.Image:
        """Read a tile from cache or download it.

        Parameters
        ----------
        x, y : int
            Tile coordinates.

        Returns
        -------
        PIL.Image.Image
            RGB tile.
        """
        path = self.tile_path(x, y)
        if path.is_file() and path.stat().st_size > 0:
            with path.open("rb") as handle:
                return Image.open(io.BytesIO(handle.read())).convert("RGB")
        request = Request(self.tile_url(x, y), headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=60) as response:
            payload = response.read()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return Image.open(io.BytesIO(payload)).convert("RGB")

    def chip(self, lon: float, lat: float, *, size: int = 96) -> NDArray[np.uint8]:
        """Extract a square chip centred on a WGS84 point.

        Parameters
        ----------
        lon, lat : float
            WGS84 coordinates.
        size : int
            Output chip side in pixels.

        Returns
        -------
        numpy.ndarray
            ``(size, size, 3)`` uint8 RGB chip.
        """
        gx, gy = self.global_pixel(lon, lat)
        left = gx - size / 2.0
        top = gy - size / 2.0
        tx0 = math.floor(left / 256.0)
        ty0 = math.floor(top / 256.0)
        tx1 = math.floor((left + size - 1) / 256.0)
        ty1 = math.floor((top + size - 1) / 256.0)
        canvas = Image.new("RGB", ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256))
        for tx in range(tx0, tx1 + 1):
            for ty in range(ty0, ty1 + 1):
                try:
                    canvas.paste(self.tile(tx, ty), ((tx - tx0) * 256, (ty - ty0) * 256))
                except OSError:
                    continue
        crop_left = left - tx0 * 256.0
        crop_top = top - ty0 * 256.0
        chip = canvas.crop(
            (
                round(crop_left),
                round(crop_top),
                round(crop_left + size),
                round(crop_top + size),
            )
        )
        return np.asarray(chip, dtype=np.uint8)


def vancouver_2022_source(cache_dir: Path) -> TileSource:
    """Return the City of Vancouver 2022 orthophoto source.

    Parameters
    ----------
    cache_dir : Path
        Tile cache root.

    Returns
    -------
    TileSource
        Source at zoom 19 (about 0.30 m/pixel).
    """
    return TileSource(
        name="vancouver_2022_orthophoto",
        service_url=(
            "https://tiles.arcgis.com/tiles/qrcTTRTwUoS8N47o/arcgis/rest/services/"
            "Orthophotos_2022/MapServer"
        ),
        zoom=19,
        cache_dir=cache_dir,
    )


def chips_for_points(
    source: TileSource,
    points: list[tuple[float, float]],
    *,
    size: int = 96,
) -> NDArray[np.uint8]:
    """Extract chips for a list of WGS84 points.

    Parameters
    ----------
    source : TileSource
        Tile source.
    points : list of tuple of float
        ``(lon, lat)`` points.
    size : int
        Chip side in pixels.

    Returns
    -------
    numpy.ndarray
        ``(N, size, size, 3)`` uint8 array.
    """
    return np.stack([source.chip(lon, lat, size=size) for lon, lat in points], axis=0)


def metro_2025_source(cache_dir: Path) -> TileSource:
    """Return the Metro Vancouver 2025 orthophoto source.

    Parameters
    ----------
    cache_dir : Path
        Tile cache root.

    Returns
    -------
    TileSource
        Source at zoom 19 (about 0.30 m/pixel).
    """
    return TileSource(
        name="metro_vancouver_2025_orthophoto",
        service_url=(
            "https://tiles.arcgis.com/tiles/qrcTTRTwUoS8N47o/arcgis/rest/services/"
            "Orthophotos_2025/MapServer"
        ),
        zoom=19,
        cache_dir=cache_dir,
    )


def coquitlam_2025_source(cache_dir: Path) -> TileSource:
    """Return the Coquitlam 2025 orthophoto source.

    Parameters
    ----------
    cache_dir : Path
        Tile cache root.

    Returns
    -------
    TileSource
        Source at zoom 19 (about 0.30 m/pixel).
    """
    return TileSource(
        name="coquitlam_2025_orthophoto",
        service_url=(
            "https://tiles.arcgis.com/tiles/Q6Lq3evZUGfPrN7o/arcgis/rest/services/"
            "Imagery_2025_MaxLOD/MapServer"
        ),
        zoom=19,
        cache_dir=cache_dir,
    )
