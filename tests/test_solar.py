"""Tests for solar position and daylight helpers."""

from __future__ import annotations

import datetime as dt

import pytest

from fresh_urban_forest.solar import (
    daylight_hours,
    parse_clock,
    parse_date,
    representative_time_grid,
    solar_noon,
    solar_position,
    sunrise_sunset,
    time_grid,
)


def test_solar_position_matches_vancouver_solstice_geometry() -> None:
    """The summer solstice sun is high and in the southern sky at local noon."""
    when = dt.datetime(2026, 6, 21, 19, 0, tzinfo=dt.UTC)
    position = solar_position(when, -123.25, 49.26)
    assert position.is_daylight
    assert 55.0 < position.altitude_deg < 65.0
    assert 120.0 < position.azimuth_deg < 190.0
    assert position.zenith_deg == pytest.approx(90.0 - position.altitude_deg)


def test_solar_position_is_night_at_midnight() -> None:
    """Midnight in Vancouver has a negative solar altitude."""
    when = dt.datetime(2026, 6, 21, 7, 0, tzinfo=dt.UTC)
    position = solar_position(when, -123.25, 49.26)
    assert not position.is_daylight
    assert position.altitude_deg < 0.0


def test_sunrise_sunset_and_daylight_hours() -> None:
    """Summer is longer than winter and both are plausible for Vancouver."""
    summer_rise, summer_set = sunrise_sunset(dt.date(2026, 6, 21), -123.25, 49.26)
    winter_rise, winter_set = sunrise_sunset(dt.date(2026, 12, 21), -123.25, 49.26)
    assert summer_rise is not None
    assert summer_set is not None
    assert winter_rise is not None
    assert winter_set is not None
    assert summer_rise < summer_set
    assert winter_rise < winter_set
    summer_hours = daylight_hours(dt.date(2026, 6, 21), -123.25, 49.26)
    winter_hours = daylight_hours(dt.date(2026, 12, 21), -123.25, 49.26)
    assert 15.0 < summer_hours < 18.0
    assert 7.0 < winter_hours < 9.5
    assert summer_hours > winter_hours


def test_parse_clock_and_date() -> None:
    """Clock and date parsing accepts the documented formats."""
    assert parse_clock("08:30") == dt.time(8, 30)
    assert parse_clock("08:30:15") == dt.time(8, 30, 15)
    assert parse_date("2026-06-21") == dt.date(2026, 6, 21)
    with pytest.raises(ValueError, match="invalid time"):
        parse_clock("8")
    with pytest.raises(ValueError, match="Invalid isoformat"):
        parse_date("June 21")


def test_time_grids_are_timezone_aware_and_ordered() -> None:
    """The day and annual grids return aware, chronologically ordered times."""
    day = time_grid(dt.date(2026, 6, 21), times=("08:00", "12:00"))
    assert len(day) == 2
    assert day[0].tzinfo is not None
    assert day[0] < day[1]
    annual = representative_time_grid(2026, months=(1, 7), times=("09:00", "15:00"))
    assert len(annual) == 4
    assert annual[0] < annual[-1]
    assert {value.month for value in annual} == {1, 7}


def test_solar_noon_matches_solstice_altitude() -> None:
    """Solar noon at the summer solstice is close to the geometric maximum."""
    noon = solar_noon(dt.date(2026, 6, 21), -123.25, 49.26)
    position = solar_position(noon, -123.25, 49.26)
    assert 62.5 < position.altitude_deg < 65.5
    assert 160.0 < position.azimuth_deg < 200.0
