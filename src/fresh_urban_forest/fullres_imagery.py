"""Full-resolution municipal orthophoto access through GDAL.

MrSID files are decoded by the local GDAL build but not by the rasterio wheel. The
scoring and training paths therefore use GDAL's Python bindings for native-resolution
window reads. Chips remain explicitly georeferenced; no stereo interpretation is made.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from osgeo import gdal  # type: ignore[import-untyped]

gdal.UseExceptions()


@dataclass
class FullResolutionSource:
    """A GDAL VRT covering full-resolution orthophoto tiles.

    Attributes
    ----------
    path : pathlib.Path
        VRT path.
    chip_px : int
        Default chip side.
    resolution_m : float
        Source pixel size in metres.
    """

    path: Path
    chip_px: int = 128
    resolution_m: float = 0.075

    def __post_init__(self) -> None:
        """Open the VRT and cache its geotransform."""
        self._dataset: Any = gdal.Open(str(self.path))
        if self._dataset is None:
            raise RuntimeError(f"could not open {self.path}")
        self._geotransform: tuple[float, ...] = self._dataset.GetGeoTransform()
        self._inverse: tuple[float, ...] = gdal.InvGeoTransform(self._geotransform)

    @property
    def width(self) -> int:
        """Return raster width.

        Returns
        -------
        int
            Width in pixels.
        """
        return int(self._dataset.RasterXSize)

    @property
    def height(self) -> int:
        """Return raster height.

        Returns
        -------
        int
            Height in pixels.
        """
        return int(self._dataset.RasterYSize)

    def chip(self, x: float, y: float, *, size: int | None = None) -> NDArray[np.uint8]:
        """Read an RGB chip centred on a projected coordinate.

        Parameters
        ----------
        x, y : float
            Coordinate in the VRT CRS (EPSG:3157 for these cities).
        size : int or None
            Chip side in pixels; defaults to ``chip_px``.

        Returns
        -------
        numpy.ndarray
            ``(size, size, 3)`` uint8 RGB chip.
        """
        side = self.chip_px if size is None else size
        px, py = gdal.ApplyGeoTransform(self._inverse, x, y)
        left = round(px - side / 2.0)
        top = round(py - side / 2.0)
        canvas = np.zeros((side, side, 3), dtype=np.uint8)
        x0 = max(left, 0)
        y0 = max(top, 0)
        x1 = min(left + side, self.width)
        y1 = min(top + side, self.height)
        if x1 <= x0 or y1 <= y0:
            return canvas
        payload = self._dataset.ReadRaster(
            x0,
            y0,
            x1 - x0,
            y1 - y0,
            buf_xsize=x1 - x0,
            buf_ysize=y1 - y0,
            band_list=[1, 2, 3],
        )
        values = np.frombuffer(payload, dtype=np.uint8).reshape(y1 - y0, x1 - x0, 3)
        canvas[y0 - top : y1 - top, x0 - left : x1 - left] = values
        return canvas

    def close(self) -> None:
        """Close the underlying GDAL dataset."""
        self._dataset = None
