"""Solar position, daylight, and time-grid helpers.

The implementation follows the NOAA solar-position equations. It is accurate enough for
site-scale shade screening (well under a degree for the intended use), but it is not a
survey-grade ephemeris. Times are evaluated in UTC and converted to a local timezone for
display.
"""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Sequence
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from fresh_urban_forest.evidence import Evidence, evidence

DEFAULT_TIMEZONE = "America/Vancouver"
DEFAULT_TIMES: tuple[str, ...] = ("08:00", "10:00", "12:00", "14:00", "16:00", "18:00")


@dataclass(frozen=True, slots=True)
class SolarPosition:
    """The sun's position at one instant.

    Attributes
    ----------
    when_utc : datetime.datetime
        The evaluation time in UTC.
    altitude_deg : float
        Solar altitude above the horizon in degrees. Negative values are night.
    azimuth_deg : float
        Solar azimuth clockwise from north in degrees.
    zenith_deg : float
        Solar zenith angle in degrees.
    declination_deg : float
        Solar declination in degrees.
    equation_of_time_min : float
        Equation of time in minutes.
    is_daylight : bool
        ``True`` when the centre of the sun is above the horizon.
    evidence : Evidence
        Method and evidence tier.
    """

    when_utc: dt.datetime
    altitude_deg: float
    azimuth_deg: float
    zenith_deg: float
    declination_deg: float
    equation_of_time_min: float
    is_daylight: bool
    evidence: Evidence

    def to_dict(self) -> dict[str, object]:
        """Convert the position to a JSON-safe dictionary.

        Returns
        -------
        dict
            Altitude, azimuth, zenith, declination, daylight flag, and evidence.
        """
        return {
            "when_utc": self.when_utc.isoformat(),
            "altitude_deg": round(self.altitude_deg, 4),
            "azimuth_deg": round(self.azimuth_deg, 4),
            "zenith_deg": round(self.zenith_deg, 4),
            "declination_deg": round(self.declination_deg, 4),
            "equation_of_time_min": round(self.equation_of_time_min, 4),
            "is_daylight": self.is_daylight,
            "evidence": self.evidence.to_dict(),
        }


def solar_position(when: dt.datetime, lon: float, lat: float) -> SolarPosition:
    """Calculate the solar position with the NOAA equations.

    Parameters
    ----------
    when : datetime.datetime
        Instant to evaluate. A naive datetime is treated as UTC; an aware datetime is
        converted to UTC.
    lon : float
        Longitude in degrees east.
    lat : float
        Latitude in degrees north.

    Returns
    -------
    SolarPosition
        Solar altitude, azimuth, and supporting quantities.
    """
    when_utc = when.replace(tzinfo=dt.UTC) if when.tzinfo is None else when.astimezone(dt.UTC)
    day_of_year = when_utc.timetuple().tm_yday
    hour = when_utc.hour + when_utc.minute / 60.0 + when_utc.second / 3600.0
    gamma = 2.0 * math.pi / 365.0 * (day_of_year - 1 + (hour - 12.0) / 24.0)
    equation = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2.0 * gamma)
        - 0.040849 * math.sin(2.0 * gamma)
    )
    declination = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2.0 * gamma)
        + 0.000907 * math.sin(2.0 * gamma)
        - 0.002697 * math.cos(3.0 * gamma)
        + 0.00148 * math.sin(3.0 * gamma)
    )
    time_offset = equation + 4.0 * lon
    true_solar_time = (hour * 60.0 + time_offset) % 1440.0
    hour_angle = true_solar_time / 4.0 - 180.0
    latitude = math.radians(lat)
    declination_rad = declination
    hour_angle_rad = math.radians(hour_angle)
    cosine_zenith = math.sin(latitude) * math.sin(declination_rad) + math.cos(latitude) * math.cos(
        declination_rad
    ) * math.cos(hour_angle_rad)
    cosine_zenith = max(-1.0, min(1.0, cosine_zenith))
    zenith = math.degrees(math.acos(cosine_zenith))
    altitude = 90.0 - zenith
    azimuth = math.degrees(
        math.atan2(
            math.sin(hour_angle_rad),
            math.cos(hour_angle_rad) * math.sin(latitude)
            - math.tan(declination_rad) * math.cos(latitude),
        )
    )
    azimuth = (azimuth + 180.0) % 360.0
    return SolarPosition(
        when_utc=when_utc,
        altitude_deg=altitude,
        azimuth_deg=azimuth,
        zenith_deg=zenith,
        declination_deg=math.degrees(declination_rad),
        equation_of_time_min=equation,
        is_daylight=altitude > 0.0,
        evidence=evidence(
            "physics",
            "noaa-solar-position",
            uncertainty="Approximate NOAA equations; not a survey-grade ephemeris.",
            source="NOAA Solar Calculator equations",
        ),
    )


def parse_clock(value: str) -> dt.time:
    """Parse a clock string such as ``08:30``.

    Parameters
    ----------
    value : str
        ``HH:MM`` or ``HH:MM:SS``.

    Returns
    -------
    datetime.time
        Parsed time.

    Raises
    ------
    ValueError
        When the string is not a valid clock time.
    """
    parts = value.strip().split(":")
    if len(parts) not in {2, 3}:
        raise ValueError(f"invalid time: {value}")
    hour = int(parts[0])
    minute = int(parts[1])
    second = int(parts[2]) if len(parts) == 3 else 0
    return dt.time(hour=hour, minute=minute, second=second)


def parse_date(value: str) -> dt.date:
    """Parse an ISO date string.

    Parameters
    ----------
    value : str
        ``YYYY-MM-DD``.

    Returns
    -------
    datetime.date
        Parsed date.

    Raises
    ------
    ValueError
        When the string is not an ISO date.
    """
    return dt.date.fromisoformat(value)


def timezone(name: str = DEFAULT_TIMEZONE) -> ZoneInfo:
    """Return a timezone object, falling back to UTC for an unknown name.

    Parameters
    ----------
    name : str
        IANA timezone name.

    Returns
    -------
    zoneinfo.ZoneInfo
        The timezone.
    """
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")


def time_grid(
    date: dt.date,
    *,
    tz: str = DEFAULT_TIMEZONE,
    times: Sequence[str] = DEFAULT_TIMES,
) -> tuple[dt.datetime, ...]:
    """Build an aware datetime grid for one day.

    Parameters
    ----------
    date : datetime.date
        Calendar date.
    tz : str
        IANA timezone name.
    times : sequence of str
        Clock strings.

    Returns
    -------
    tuple of datetime.datetime
        Aware local datetimes.
    """
    zone = timezone(tz)
    return tuple(dt.datetime.combine(date, parse_clock(value), tzinfo=zone) for value in times)


def representative_time_grid(
    year: int,
    *,
    tz: str = DEFAULT_TIMEZONE,
    months: Sequence[int] = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12),
    day: int = 15,
    times: Sequence[str] = ("09:00", "12:00", "15:00", "18:00"),
) -> tuple[dt.datetime, ...]:
    """Build a representative annual time grid.

    Parameters
    ----------
    year : int
        Calendar year.
    tz : str
        IANA timezone name.
    months : sequence of int
        Months to sample.
    day : int
        Day of month used for every sample.
    times : sequence of str
        Clock strings.

    Returns
    -------
    tuple of datetime.datetime
        Aware local datetimes, ordered by month and time.
    """
    zone = timezone(tz)
    result: list[dt.datetime] = []
    for month in months:
        date = dt.date(year, month, min(day, 28))
        for value in times:
            result.append(dt.datetime.combine(date, parse_clock(value), tzinfo=zone))
    return tuple(result)


def solar_noon(date: dt.date, lon: float, lat: float, *, tz: str = DEFAULT_TIMEZONE) -> dt.datetime:
    """Estimate solar noon for a date and location.

    Parameters
    ----------
    date : datetime.date
        Calendar date.
    lon : float
        Longitude in degrees east.
    lat : float
        Latitude in degrees north.
    tz : str
        IANA timezone name.

    Returns
    -------
    datetime.datetime
        Aware local time of solar noon.
    """
    zone = timezone(tz)
    noon_utc = dt.datetime.combine(date, dt.time(12, 0), tzinfo=dt.UTC)
    position = solar_position(noon_utc, lon, lat)
    # The equation of time and longitude correction shift solar noon from 12:00 UTC.
    offset_minutes = 720.0 - (position.equation_of_time_min + 4.0 * lon)
    candidate = dt.datetime.combine(date, dt.time(0, 0), tzinfo=dt.UTC) + dt.timedelta(
        minutes=offset_minutes
    )
    return candidate.astimezone(zone)


def sunrise_sunset(
    date: dt.date,
    lon: float,
    lat: float,
    *,
    tz: str = DEFAULT_TIMEZONE,
) -> tuple[dt.datetime | None, dt.datetime | None]:
    """Estimate sunrise and sunset for a date and location.

    Parameters
    ----------
    date : datetime.date
        Calendar date.
    lon : float
        Longitude in degrees east.
    lat : float
        Latitude in degrees north.
    tz : str
        IANA timezone name.

    Returns
    -------
    tuple of datetime.datetime or None
        Sunrise and sunset in local time, or ``(None, None)`` during polar day/night.
    """
    noon_utc = dt.datetime.combine(date, dt.time(12, 0), tzinfo=dt.UTC)
    position = solar_position(noon_utc, lon, lat)
    latitude = math.radians(lat)
    declination = math.radians(position.declination_deg)
    cosine_hour_angle = -math.tan(latitude) * math.tan(declination)
    if cosine_hour_angle < -1.0 or cosine_hour_angle > 1.0:
        return (None, None)
    hour_angle = math.degrees(math.acos(cosine_hour_angle))
    sunrise_minutes = 720.0 - 4.0 * (lon + hour_angle) - position.equation_of_time_min
    sunset_minutes = 720.0 - 4.0 * (lon - hour_angle) - position.equation_of_time_min
    midnight = dt.datetime.combine(date, dt.time(0, 0), tzinfo=dt.UTC)
    zone = timezone(tz)
    sunrise = (midnight + dt.timedelta(minutes=sunrise_minutes)).astimezone(zone)
    sunset = (midnight + dt.timedelta(minutes=sunset_minutes)).astimezone(zone)
    return (sunrise, sunset)


def daylight_hours(date: dt.date, lon: float, lat: float, *, tz: str = DEFAULT_TIMEZONE) -> float:
    """Calculate daylight duration for a date and location.

    Parameters
    ----------
    date : datetime.date
        Calendar date.
    lon : float
        Longitude in degrees east.
    lat : float
        Latitude in degrees north.
    tz : str
        IANA timezone name.

    Returns
    -------
    float
        Daylight duration in hours, or zero during polar night.
    """
    sunrise, sunset = sunrise_sunset(date, lon, lat, tz=tz)
    if sunrise is None or sunset is None:
        return 0.0
    return max(0.0, (sunset - sunrise).total_seconds() / 3600.0)
