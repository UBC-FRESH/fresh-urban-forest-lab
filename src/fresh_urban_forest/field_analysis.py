"""Analyse a completed field-validation packet.

The analysis is intentionally explicit about the reference population: only inventory
trees and detected crowns that a field crew actually checked are used for precision and
recall. Blank rows stay in the packet but are reported as unverified.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean

from fresh_urban_forest.validation import VALIDATION_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class FieldValidation:
    """Summary of a completed field packet.

    Attributes
    ----------
    schema_version : str
        Result schema.
    inventory_rows : int
        Inventory tree rows in the checklist.
    verified_present : int
        Inventory trees confirmed present.
    missing_trees : int
        Inventory trees not found.
    new_trees : int
        Live trees found that were not in the inventory.
    unverified_trees : int
        Inventory rows left blank.
    detected_rows : int
        Detected crowns in the checklist.
    detected_real : int
        Detected crowns confirmed as real trees.
    detected_merged : int
        Detected crowns that merge two or more real crowns.
    detected_false_positive : int
        Detected crowns confirmed as false positives.
    detected_unverified : int
        Detected crowns left blank.
    precision : float
        Real detected crowns divided by evaluated detected crowns.
    precision_including_merged : float
        Real plus merged crowns divided by evaluated detected crowns.
    recall : float
        Verified present plus new trees divided by verified present, missing, and new.
    mean_height_bias_m : float
        Detected minus field height on matched rows with a field height.
    mean_crown_radius_bias_m : float
        Detected minus field crown radius on matched rows with a field crown width.
    notes : tuple of str
        Interpretation caveats.
    """

    schema_version: str
    inventory_rows: int
    verified_present: int
    missing_trees: int
    new_trees: int
    unverified_trees: int
    detected_rows: int
    detected_real: int
    detected_merged: int
    detected_false_positive: int
    detected_unverified: int
    precision: float
    precision_including_merged: float
    recall: float
    mean_height_bias_m: float
    mean_crown_radius_bias_m: float
    notes: tuple[str, ...]


def analyze_field_packet(packet_dir: Path) -> FieldValidation:
    """Analyse a completed field packet.

    Parameters
    ----------
    packet_dir : Path
        Directory containing ``field_checks.csv`` and ``detected_checks.csv``.

    Returns
    -------
    FieldValidation
        Summary metrics.

    Raises
    ------
    FileNotFoundError
        When either CSV is missing.
    """
    inventory_path = packet_dir / "field_checks.csv"
    detected_path = packet_dir / "detected_checks.csv"
    if not inventory_path.is_file():
        raise FileNotFoundError(f"missing {inventory_path}")
    if not detected_path.is_file():
        raise FileNotFoundError(f"missing {detected_path}")
    inventory = _read_rows(inventory_path)
    detected = _read_rows(detected_path)
    verified_present = sum(1 for row in inventory if _status(row.get("field_verified")) == "yes")
    missing = sum(1 for row in inventory if _status(row.get("field_verified")) == "missing")
    new = sum(1 for row in inventory if _status(row.get("field_verified")) == "new")
    unverified = sum(1 for row in inventory if _status(row.get("field_verified")) == "blank")
    real = sum(1 for row in detected if _status(row.get("field_status")) == "real")
    merged = sum(1 for row in detected if _status(row.get("field_status")) == "merged")
    false_positive = sum(
        1 for row in detected if _status(row.get("field_status")) == "false_positive"
    )
    detected_unverified = sum(1 for row in detected if _status(row.get("field_status")) == "blank")
    evaluated_detected = real + merged + false_positive
    reference_trees = verified_present + missing + new
    precision = real / evaluated_detected if evaluated_detected else 0.0
    precision_merged = (real + merged) / evaluated_detected if evaluated_detected else 0.0
    recall = (verified_present + new) / reference_trees if reference_trees else 0.0
    height_deltas = [
        _float(row.get("detected_height_m")) - _float(row.get("field_height_m"))
        for row in inventory
        if _status(row.get("field_verified")) == "yes"
        and _float_or_none(row.get("detected_height_m")) is not None
        and _float_or_none(row.get("field_height_m")) is not None
    ]
    crown_deltas = [
        _float(row.get("detected_crown_radius_m")) - _float(row.get("field_crown_width_m")) / 2.0
        for row in inventory
        if _status(row.get("field_verified")) == "yes"
        and _float_or_none(row.get("detected_crown_radius_m")) is not None
        and _float_or_none(row.get("field_crown_width_m")) is not None
    ]
    return FieldValidation(
        schema_version=VALIDATION_SCHEMA_VERSION,
        inventory_rows=len(inventory),
        verified_present=verified_present,
        missing_trees=missing,
        new_trees=new,
        unverified_trees=unverified,
        detected_rows=len(detected),
        detected_real=real,
        detected_merged=merged,
        detected_false_positive=false_positive,
        detected_unverified=detected_unverified,
        precision=round(precision, 4),
        precision_including_merged=round(precision_merged, 4),
        recall=round(recall, 4),
        mean_height_bias_m=round(mean(height_deltas), 3) if height_deltas else 0.0,
        mean_crown_radius_bias_m=round(mean(crown_deltas), 3) if crown_deltas else 0.0,
        notes=(
            "Only field-verified rows enter precision and recall.",
            "Merged crowns are reported separately from real and false-positive crowns.",
            "A complete reference patch is still a sample; do not extrapolate without design "
            "weights.",
        ),
    )


def write_field_analysis(result: FieldValidation, out_dir: Path) -> Path:
    """Write the field analysis as JSON and Markdown.

    Parameters
    ----------
    result : FieldValidation
        Analysis result.
    out_dir : Path
        Destination directory.

    Returns
    -------
    Path
        The written JSON path.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "field_analysis.json"
    path.write_text(json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8")
    (out_dir / "field_analysis.md").write_text(_markdown(result), encoding="utf-8")
    return path


def _read_rows(path: Path) -> list[dict[str, str]]:
    """Read a CSV as dictionaries.

    Parameters
    ----------
    path : Path
        CSV path.

    Returns
    -------
    list of dict
        Rows with stripped values.
    """
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [
            {key: (value or "").strip() for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]


def _status(value: str | None) -> str:
    """Normalise a field status.

    Parameters
    ----------
    value : str or None
        Raw status.

    Returns
    -------
    str
        ``yes``, ``missing``, ``new``, ``real``, ``merged``,
        ``false_positive``, or ``blank``.
    """
    text = (value or "").strip().lower().replace(" ", "_")
    if text in {"yes", "present", "verified", "true"}:
        return "yes"
    if text in {"missing", "no", "absent"}:
        return "missing"
    if text in {"new", "added"}:
        return "new"
    if text in {"real", "tree", "true_positive"}:
        return "real"
    if text in {"merged", "merge", "combined"}:
        return "merged"
    if text in {"false_positive", "false", "fp", "not_a_tree"}:
        return "false_positive"
    return "blank"


def _float(value: str | None) -> float:
    """Convert a CSV value to a float, defaulting to zero.

    Parameters
    ----------
    value : str or None
        Candidate value.

    Returns
    -------
    float
        The value, or zero.
    """
    return _float_or_none(value) or 0.0


def _float_or_none(value: str | None) -> float | None:
    """Convert a CSV value to an optional float.

    Parameters
    ----------
    value : str or None
        Candidate value.

    Returns
    -------
    float or None
        The value, or ``None``.
    """
    if value is None or not value.strip():
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _markdown(result: FieldValidation) -> str:
    """Render the field analysis as Markdown.

    Parameters
    ----------
    result : FieldValidation
        Analysis result.

    Returns
    -------
    str
        Markdown report.
    """
    return (
        f"""# Field validation result

- Inventory rows: {result.inventory_rows}
- Verified present: {result.verified_present}
- Missing trees: {result.missing_trees}
- New trees found: {result.new_trees}
- Unverified inventory rows: {result.unverified_trees}
- Detected crowns: {result.detected_rows}
- Real / merged / false positive / unverified:
  {result.detected_real} / {result.detected_merged} /
  {result.detected_false_positive} / {result.detected_unverified}

## Metrics

- Precision (real only): **{result.precision}**
- Precision (real + merged): **{result.precision_including_merged}**
- Recall: **{result.recall}**
- Mean height bias: **{result.mean_height_bias_m} m**
- Mean crown-radius bias: **{result.mean_crown_radius_bias_m} m**

## Notes

"""
        + "\n".join(f"- {note}" for note in result.notes)
        + "\n"
    )
