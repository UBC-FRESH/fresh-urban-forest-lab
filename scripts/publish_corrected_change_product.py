#!/usr/bin/env python3
"""Publish a corrected change product as a selectable dataset sidecar.

The product is copied as ``change_control.json`` and ``change_control.png`` so the
existing change-product selector can list it without replacing the original product.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Parameters
    ----------
    argv : list of str or None
        Arguments. ``None`` uses ``sys.argv``.

    Returns
    -------
    argparse.Namespace
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args(argv)


def publish(source_dir: Path, out_dir: Path) -> dict[str, str]:
    """Copy a corrected change product into a dataset root.

    Parameters
    ----------
    source_dir : Path
        Corrected product directory.
    out_dir : Path
        Dataset root that the service serves.

    Returns
    -------
    dict
        Written paths.

    Raises
    ------
    FileNotFoundError
        When the source summary or PNG is missing.
    """
    summary = source_dir / "change.json"
    image = source_dir / "change.png"
    if not summary.exists() or not image.exists():
        raise FileNotFoundError("corrected product needs change.json and change.png")
    out_dir.mkdir(parents=True, exist_ok=True)
    target_summary = out_dir / "change_control.json"
    target_image = out_dir / "change_control.png"
    target_meta = out_dir / "canopy_change_control_meta.json"
    shutil.copy2(summary, target_summary)
    shutil.copy2(image, target_image)
    metadata = {
        "source": str(source_dir),
        "product": "control-corrected",
        "summary": target_summary.name,
        "image": target_image.name,
        "status": "selectable sidecar; original product remains default",
    }
    target_meta.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return {
        "summary": str(target_summary),
        "image": str(target_image),
        "metadata": str(target_meta),
    }


def main(argv: list[str] | None = None) -> int:
    """Publish a corrected change sidecar.

    Parameters
    ----------
    argv : list of str or None
        Command-line arguments.

    Returns
    -------
    int
        Zero on success.
    """
    args = parse_args(argv)
    print(json.dumps(publish(args.source_dir, args.out_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
