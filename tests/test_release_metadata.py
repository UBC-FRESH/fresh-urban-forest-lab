"""Release metadata consistency checks."""

from __future__ import annotations

import re
from pathlib import Path

from fresh_urban_forest import __version__

ROOT = Path(__file__).resolve().parents[1]


def _declared_version(path: Path, pattern: str) -> str:
    """Return the first captured version string from a metadata file."""
    match = re.search(pattern, path.read_text(encoding="utf-8"), flags=re.MULTILINE)
    assert match is not None, f"version pattern not found in {path.name}"
    return match.group(1)


def test_release_versions_match() -> None:
    """Package, citation, runtime, and release-note versions stay aligned."""
    package = _declared_version(ROOT / "pyproject.toml", r'^version = "([^"]+)"')
    citation = _declared_version(ROOT / "CITATION.cff", r'^version: "([^"]+)"')
    runtime = _declared_version(
        ROOT / "src" / "fresh_urban_forest" / "__init__.py",
        r'^__version__ = "([^"]+)"',
    )
    assert package == citation == runtime == __version__
    assert (ROOT / "notes" / "releases" / f"v{__version__}.md").is_file()
