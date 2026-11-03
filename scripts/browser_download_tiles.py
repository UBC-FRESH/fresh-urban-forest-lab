#!/usr/bin/env python3
"""Download tiles with a headed Chromium where a site blocks HTTP clients.

Some municipal download hosts put a Cloudflare challenge in front of large ZIP files.
A headed Chromium can pass the challenge where ``curl`` and ``httpx`` receive a 403. This
script is an operator tool, not part of the normal ingestion path. Run it under Xvfb on a
headless server:

    xvfb-run -a python scripts/browser_download_tiles.py \
      --manifest data/raw/tiles/vancouver_2022_ubc.json \
      --dest data/raw/city_lidar/2022

The script does not bypass authentication. It uses a normal browser session and records
the file it saves.
"""

from __future__ import annotations

import argparse
import contextlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from playwright.sync_api import sync_playwright

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def load_manifest(path: Path) -> list[Mapping[str, object]]:
    """Read tile records from a manifest.

    Parameters
    ----------
    path : Path
        Tile manifest JSON.

    Returns
    -------
    list of mapping
        Tile records.

    Raises
    ------
    ValueError
        When the payload has no tile list.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    tiles = payload.get("tiles", [])
    if not isinstance(tiles, list):
        raise ValueError("tile manifest has no tiles list")
    return [tile for tile in tiles if isinstance(tile, Mapping)]


def download_with_browser(  # pragma: no cover - operator-only browser path
    url: str,
    destination: Path,
    *,
    timeout_ms: int = 180_000,
    headless: bool = False,
) -> Path:
    """Download one URL through a headed Chromium session.

    Parameters
    ----------
    url : str
        Download URL.
    destination : Path
        Destination file.
    timeout_ms : int
        Download timeout in milliseconds.
    headless : bool
        When ``False``, use a visible browser. A visible browser is more likely to pass a
        Cloudflare challenge; use ``xvfb-run`` on a headless host.

    Returns
    -------
    Path
        The saved file.

    Raises
    ------
    RuntimeError
        When no download starts.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            accept_downloads=True,
            user_agent=USER_AGENT,
        )
        page = context.new_page()
        try:
            with page.expect_download(timeout=timeout_ms) as info, contextlib.suppress(Exception):
                page.goto(url, wait_until="commit", timeout=timeout_ms)
            download = info.value
            download.save_as(destination)
        except Exception as exc:
            raise RuntimeError(f"browser download failed for {url}: {exc}") from exc
        finally:
            browser.close()
    return destination


def main(argv: Sequence[str] | None = None) -> int:
    """Run the browser downloader.

    Parameters
    ----------
    argv : sequence of str or None
        Command-line arguments.

    Returns
    -------
    int
        Zero on success.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, help="tile manifest JSON")
    parser.add_argument("--dest", type=Path, required=True, help="destination directory")
    parser.add_argument("--url", help="single download URL")
    parser.add_argument("--out", type=Path, help="single output path")
    parser.add_argument("--headless", action="store_true", help="use headless Chromium")
    args = parser.parse_args(argv)
    if args.manifest is not None:
        for tile in load_manifest(args.manifest):
            url = str(tile.get("url", ""))
            source = str(tile.get("source", "tiles"))
            filename = str(tile.get("filename", "tile.bin"))
            if not url:
                continue
            path = download_with_browser(
                url,
                args.dest / source / filename,
                headless=args.headless,
            )
            print(f"saved {path} ({path.stat().st_size} bytes)")
        return 0
    if args.url and args.out:
        path = download_with_browser(args.url, args.out, headless=args.headless)
        print(f"saved {path} ({path.stat().st_size} bytes)")
        return 0
    parser.error("pass --manifest, or both --url and --out")


if __name__ == "__main__":
    raise SystemExit(main())
