"""Tests for the open Census equity screen."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import box

from fresh_urban_forest.census import (
    build_equity_frame,
    combine_profiles,
    equity_summary,
    read_profile_csv,
)

CRS = "EPSG:3157"


def _write_profile(
    path: Path,
    characteristic: str,
    statistic: str,
    rows: list[tuple[str, str]],
) -> None:
    """Write a tiny Census Profile CSV fixture."""
    lines = ["DATAFLOW,FREQ,TIME_PERIOD,REF_AREA,GENDER,CHARACTERISTIC,STATISTIC,OBS_VALUE"]
    for index, (area, value) in enumerate(rows):
        lines.append(f"STC_CP:DF_DA(1.3),A5,2021,{area},1,{characteristic},{statistic},{value}")
        if index == 0:
            lines.append(f"STC_CP:DF_DA(1.3),A5,2021,{area},1,{characteristic},99,{value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _profiles() -> dict[str, dict[str, float]]:
    """Return a minimal two-area profile set."""
    return {
        "population": {"d1": 500.0, "d2": 500.0},
        "age_0_14": {"d1": 50.0, "d2": 100.0},
        "age_15_64": {"d1": 400.0, "d2": 350.0},
        "age_65_plus": {"d1": 50.0, "d2": 50.0},
        "median_income": {"d1": 80_000.0, "d2": 40_000.0},
        "visible_minority_total": {"d1": 500.0, "d2": 500.0},
        "visible_minority": {"d1": 50.0, "d2": 250.0},
        "unemployment_rate": {"d1": 4.0, "d2": 12.0},
    }


def test_read_profile_csv_filters_characteristic_and_statistic(tmp_path: Path) -> None:
    """The reader keeps one row per area and ignores other statistics."""
    path = tmp_path / "profile.csv"
    _write_profile(path, "113", "1", [("d1", "50000"), ("d2", "")])
    values = read_profile_csv(path, "113", "1")
    assert values["d1"] == pytest.approx(50000.0)
    assert np.isnan(values["d2"])


def test_read_profile_csv_rejects_missing_columns(tmp_path: Path) -> None:
    """A malformed export is rejected with a useful error."""
    path = tmp_path / "bad.csv"
    path.write_text("REF_AREA,OBS_VALUE\nd1,1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        read_profile_csv(path, "113", "1")


def test_combine_profiles_uses_reference_area_and_direction() -> None:
    """Higher need produces a higher score, and income is inverted."""
    table = combine_profiles(_profiles(), reference={"d1", "d2"})
    scores = table["equity_score"].to_dict()
    income_need = table["median_income_need"].to_dict()
    age_need = table["age_dependency_need"].to_dict()
    assert float(scores["d2"]) > float(scores["d1"])
    assert float(income_need["d2"]) > float(income_need["d1"])
    assert float(age_need["d2"]) > float(age_need["d1"])


def test_combine_profiles_rejects_bad_minimum() -> None:
    """The score requires at least one indicator."""
    with pytest.raises(ValueError, match="positive"):
        combine_profiles(_profiles(), minimum_indicators=0)


def test_combine_profiles_rejects_missing_indicator() -> None:
    """A missing input is not silently ignored."""
    profiles = _profiles()
    del profiles["median_income"]
    with pytest.raises(ValueError, match="missing Census indicators"):
        combine_profiles(profiles)


def test_build_equity_frame_and_summary() -> None:
    """The join preserves geometry and the summary reports valid areas."""
    geometry = gpd.GeoDataFrame(
        {"DGUID": ["d1", "d2"]},
        geometry=[box(0, 0, 100, 100), box(100, 0, 200, 100)],
        crs=CRS,
    )
    frame = build_equity_frame(geometry, _profiles())
    assert len(frame) == 2
    assert frame.crs == CRS
    assert frame["equity_score"].notna().all()
    summary = equity_summary(frame)
    assert summary["areas"] == 2
    assert summary["areas_with_score"] == 2
    assert summary["indicators"] == [
        "median_income",
        "age_dependency",
        "visible_minority_share",
        "unemployment_rate",
    ]
    evidence_summary = cast("dict[str, object]", summary["evidence"])
    assert evidence_summary["tier"] == "measured"


def test_build_equity_frame_requires_id_and_crs() -> None:
    """A frame without an ID or CRS cannot be joined."""
    geometry = gpd.GeoDataFrame({"other": ["d1"]}, geometry=[box(0, 0, 1, 1)], crs=CRS)
    with pytest.raises(ValueError, match="DGUID"):
        build_equity_frame(geometry, _profiles())
    no_crs = gpd.GeoDataFrame({"DGUID": ["d1"]}, geometry=[box(0, 0, 1, 1)], crs=None)
    with pytest.raises(ValueError, match="CRS"):
        build_equity_frame(no_crs, _profiles())
