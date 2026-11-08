#!/usr/bin/env python3
"""Select a deterministic spatial sample of Vancouver 2018 LiDAR tiles.

The selection uses one smallest ZIP per populated 6 x 6 longitude/latitude bin. It records
the rule, checksums, bboxes, sizes, and URLs in a manifest for reproducible download.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

CITY_BOUNDS_WGS84 = (-123.2245147558162, 49.198787026639735, -123.02319017231899, 49.29589052229097)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Parameters
    ----------
    argv : sequence of str or None
        Arguments. ``None`` uses ``sys.argv``.

    Returns
    -------
    argparse.Namespace
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--index",
        type=Path,
        default=Path(
            "/srv/shared-data/gep/ws4/p43-worktree/data/raw/tiles/vancouver_2018_city.json"
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/raw/tiles/control_sample_manifest.json"),
    )
    parser.add_argument("--bins", type=int, default=6)
    parser.add_argument("--min-tiles", type=int, default=30)
    parser.add_argument("--max-tiles", type=int, default=50)
    return parser.parse_args(argv)


def _tile_size(tile: dict[str, object]) -> float:
    """Return a numeric tile size for deterministic ordering."""
    value = tile.get("size_bytes", 0)
    return float(value) if isinstance(value, (int, float)) else 0.0


def select_tiles(
    tiles: Sequence[dict[str, object]],
    *,
    bounds: tuple[float, float, float, float],
    bins: int,
    min_tiles: int,
    max_tiles: int,
) -> list[dict[str, object]]:
    """Select the smallest tile in each populated spatial bin.

    Parameters
    ----------
    tiles : sequence of mapping
        Index records with ``bbox`` and ``size_bytes``.
    bounds : tuple of float
        Longitude/latitude city bounds.
    bins : int
        Number of bins per axis.
    min_tiles : int
        Minimum accepted selection size.
    max_tiles : int
        Maximum accepted selection size.

    Returns
    -------
    list of dict
        Selected records with a ``selection_bin`` field.

    Raises
    ------
    ValueError
        When the bounds or target size are invalid or the selection is out of bounds.
    """
    left, bottom, right, top = bounds
    if right <= left or top <= bottom or bins < 2:
        raise ValueError("bounds and bins must be positive")
    if min_tiles < 1 or max_tiles < min_tiles:
        raise ValueError("tile limits must be positive and ordered")
    grouped: dict[tuple[int, int], list[dict[str, object]]] = {}
    for tile in tiles:
        bbox = tile.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        values = [float(value) for value in bbox]
        lon = (values[0] + values[2]) / 2.0
        lat = (values[1] + values[3]) / 2.0
        if not (left <= lon <= right and bottom <= lat <= top):
            continue
        col = min(bins - 1, int((lon - left) / (right - left) * bins))
        row = min(bins - 1, int((lat - bottom) / (top - bottom) * bins))
        grouped.setdefault((row, col), []).append(tile)
    selected = []
    for (row, col), candidates in sorted(grouped.items()):
        chosen = min(candidates, key=_tile_size)
        selected.append({**chosen, "selection_bin": [row, col]})
    if len(selected) < min_tiles or len(selected) > max_tiles:
        raise ValueError(
            f"selection produced {len(selected)} tiles; expected {min_tiles}-{max_tiles}"
        )
    return selected


def main(argv: Sequence[str] | None = None) -> int:
    """Write the deterministic control-sample manifest.

    Parameters
    ----------
    argv : sequence of str or None
        Command-line arguments.

    Returns
    -------
    int
        Zero on success.
    """
    args = parse_args(argv)
    index = json.loads(args.index.read_text(encoding="utf-8"))
    selected = select_tiles(
        index.get("tiles", []),
        bounds=CITY_BOUNDS_WGS84,
        bins=args.bins,
        min_tiles=args.min_tiles,
        max_tiles=args.max_tiles,
    )
    payload = {
        "schema_version": "fresh-urban-forest.control-tile-sample.v1",
        "source": index.get("source"),
        "bounds_wgs84": list(CITY_BOUNDS_WGS84),
        "selection_rule": (
            "one smallest 2018 ZIP per populated 6x6 longitude/latitude bin; "
            "tile centre inside P43 city bounds"
        ),
        "tile_count": len(selected),
        "tiles": selected,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"tile_count": len(selected), "out": str(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
