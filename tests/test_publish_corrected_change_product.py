"""Tests for publishing a corrected change sidecar."""

from __future__ import annotations

import json
from pathlib import Path

from publish_corrected_change_product import publish


def test_publish_copies_selectable_sidecar(tmp_path: Path) -> None:
    """The corrected product is copied without replacing the original."""
    source = tmp_path / "corrected"
    source.mkdir()
    (source / "change.json").write_text('{"earlier_label": "corrected"}', encoding="utf-8")
    (source / "change.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    out = tmp_path / "dataset"
    out.mkdir()
    (out / "change.json").write_text('{"earlier_label": "original"}', encoding="utf-8")
    paths = publish(source, out)
    assert (out / "change_control.json").exists()
    assert (out / "change_control.png").exists()
    assert (out / "change.json").read_text(encoding="utf-8") == '{"earlier_label": "original"}'
    metadata = json.loads((out / "canopy_change_control_meta.json").read_text(encoding="utf-8"))
    assert metadata["product"] == "control-corrected"
    assert paths["summary"].endswith("change_control.json")
