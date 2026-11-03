"""Tests for the optional browser-assisted tile downloader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from browser_download_tiles import load_manifest, main


def test_load_manifest_reads_tiles(tmp_path: Path) -> None:
    """A manifest is read into tile mappings."""
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps({"tiles": [{"url": "https://example.test/a.zip"}]}), encoding="utf-8"
    )
    tiles = load_manifest(path)
    assert tiles[0]["url"] == "https://example.test/a.zip"


def test_load_manifest_rejects_malformed_payload(tmp_path: Path) -> None:
    """A payload without a tile list is refused."""
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"tiles": "no"}), encoding="utf-8")
    with pytest.raises(ValueError, match="tiles list"):
        load_manifest(path)


def test_main_downloads_manifest_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The manifest path calls the browser helper for each tile."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "tiles": [
                    {
                        "source": "vancouver-lidar-2022",
                        "filename": "tile.zip",
                        "url": "https://example.test/tile.zip",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    def fake_download(url: str, destination: Path, **kwargs: object) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"tile")
        return destination

    monkeypatch.setattr("browser_download_tiles.download_with_browser", fake_download)
    assert main(["--manifest", str(manifest), "--dest", str(tmp_path / "out")]) == 0
    assert (tmp_path / "out" / "vancouver-lidar-2022" / "tile.zip").read_bytes() == b"tile"


def test_main_downloads_single_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The single-URL path is supported for a quick operator retry."""

    def fake_download(url: str, destination: Path, **kwargs: object) -> Path:
        destination.write_bytes(b"tile")
        return destination

    monkeypatch.setattr("browser_download_tiles.download_with_browser", fake_download)
    out = tmp_path / "tile.zip"
    assert (
        main(["--url", "https://example.test/tile.zip", "--out", str(out), "--dest", str(tmp_path)])
        == 0
    )
    assert out.read_bytes() == b"tile"


def test_main_requires_an_input() -> None:
    """Missing arguments are a usage error."""
    with pytest.raises(SystemExit):
        main(["--dest", "/tmp/out"])
