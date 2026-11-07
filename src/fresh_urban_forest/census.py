"""Open 2021 Census indicators for a transparent social-equity screen.

The module reads the public Statistics Canada Census Profile dissemination-area
tables and combines four indicators that are available without a commercial
subscription: median household income, age dependency, visible-minority share,
and unemployment rate. It deliberately does not reproduce a proprietary tree
equity index or add land-surface temperature; those are separate inputs.

The percentile ranks are computed only across the reference dissemination areas
that the caller supplies, normally the city being analysed. That prevents a
Vancouver score from being diluted by the rest of Canada.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from fresh_urban_forest.evidence import evidence

CENSUS_EVIDENCE = evidence(
    "measured",
    "statcan-2021-da-census-profile",
    uncertainty=(
        "Census indicators describe residents, not trees. Income and labour values are "
        "survey estimates, some small areas are suppressed, and the index is a relative "
        "screen rather than a needs assessment."
    ),
    source=(
        "Statistics Canada, Census Profile 2021, dissemination areas; "
        "https://www12.statcan.gc.ca/census-recensement/2021/dp-pd/prof/"
    ),
)

PROFILE_COLUMNS = (
    "REF_AREA",
    "CHARACTERISTIC",
    "STATISTIC",
    "OBS_VALUE",
)
PROFILE_SPECS: Mapping[str, tuple[str, str]] = {
    "population": ("1", "1"),
    "age_0_14": ("9", "1"),
    "age_15_64": ("13", "1"),
    "age_65_plus": ("24", "1"),
    "median_income": ("113", "1"),
    "visible_minority_total": ("1669", "1"),
    "visible_minority": ("1670", "1"),
    "unemployment_rate": ("2230", "4"),
}
NEED_INDICATORS = (
    "median_income",
    "age_dependency",
    "visible_minority_share",
    "unemployment_rate",
)


def read_profile_csv(
    path: Path,
    characteristic: str,
    statistic: str,
) -> dict[str, float]:
    """Read one Census Profile characteristic from an SDMX CSV export.

    Parameters
    ----------
    path : Path
        CSV exported from the Statistics Canada Census Profile SDMX endpoint.
    characteristic : str
        Census characteristic code, for example ``"113"`` for median income.
    statistic : str
        Statistic code, for example ``"1"`` for counts or ``"4"`` for rates.

    Returns
    -------
    dict of str to float
        Dissemination-area geography ID to observed value. Suppressed or empty
        values are returned as ``numpy.nan``.

    Raises
    ------
    ValueError
        When the CSV does not have the expected columns.
    """
    frame = pd.read_csv(path, dtype={"REF_AREA": str, "CHARACTERISTIC": str, "STATISTIC": str})
    missing = [column for column in PROFILE_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Census Profile CSV is missing columns: {', '.join(missing)}")
    subset = frame.loc[
        (frame["CHARACTERISTIC"] == characteristic) & (frame["STATISTIC"] == statistic),
        ["REF_AREA", "OBS_VALUE"],
    ].drop_duplicates("REF_AREA")
    values = pd.to_numeric(subset["OBS_VALUE"], errors="coerce")
    return {str(area): float(value) for area, value in zip(subset["REF_AREA"], values, strict=True)}


def load_profiles(directory: Path) -> dict[str, dict[str, float]]:
    """Load all configured Census Profile characteristics from a directory.

    The directory must contain the files written by the documented download
    command, named ``cp_<characteristic>.<statistic>.csv``.

    Parameters
    ----------
    directory : Path
        Directory containing the Census Profile CSV exports.

    Returns
    -------
    dict of str to dict of str to float
        Indicator name to dissemination-area values.

    Raises
    ------
    FileNotFoundError
        When one of the configured files is absent.
    """
    profiles: dict[str, dict[str, float]] = {}
    for name, (characteristic, statistic) in PROFILE_SPECS.items():
        path = directory / f"cp_{characteristic}.{statistic}.csv"
        if not path.exists():
            raise FileNotFoundError(path)
        profiles[name] = read_profile_csv(path, characteristic, statistic)
    return profiles


def combine_profiles(
    profiles: Mapping[str, Mapping[str, float]],
    *,
    reference: Iterable[str] | None = None,
    minimum_indicators: int = 3,
) -> pd.DataFrame:
    """Combine Census indicators into a relative social-equity score.

    Parameters
    ----------
    profiles : mapping
        Indicator name to dissemination-area values. Required keys are listed in
        :data:`PROFILE_SPECS`.
    reference : iterable of str or None
        Dissemination-area IDs used to calculate percentile ranks. When omitted,
        every area in ``profiles`` is used.
    minimum_indicators : int
        Minimum number of available need indicators required for a score.

    Returns
    -------
    pandas.DataFrame
        One row per dissemination area with the raw indicators, need
        percentiles, and ``equity_score``. Higher scores mean greater relative
        need.

    Raises
    ------
    ValueError
        When a required indicator is missing or ``minimum_indicators`` is not
        positive.
    """
    if minimum_indicators < 1:
        raise ValueError("minimum_indicators must be positive")
    missing = [name for name in PROFILE_SPECS if name not in profiles]
    if missing:
        raise ValueError(f"missing Census indicators: {', '.join(missing)}")

    index = sorted({area for values in profiles.values() for area in values})
    frame = pd.DataFrame(index=pd.Index(index, name="dguid"))
    for name in PROFILE_SPECS:
        frame[name] = pd.Series(profiles[name], dtype="float64").reindex(frame.index)
    frame["age_dependency"] = (
        frame["age_0_14"].fillna(0.0) + frame["age_65_plus"].fillna(0.0)
    ) / frame["age_15_64"].replace(0.0, np.nan)
    frame["visible_minority_share"] = frame["visible_minority"] / frame[
        "visible_minority_total"
    ].replace(0.0, np.nan)

    reference_ids = set(reference) & set(frame.index) if reference is not None else set(frame.index)
    if not reference_ids:
        raise ValueError("reference contains no dissemination areas in the profiles")
    reference_mask = frame.index.isin(reference_ids)
    need_columns: list[str] = []
    for name in NEED_INDICATORS:
        percentile = frame.loc[reference_mask, name].rank(pct=True)
        need = percentile.reindex(frame.index)
        if name == "median_income":
            need = 1.0 - need
        column = f"{name}_need"
        frame[column] = need.astype("float64")
        need_columns.append(column)
    frame["equity_score"] = frame[need_columns].mean(axis=1, skipna=True)
    available = frame[need_columns].notna().sum(axis=1)
    frame.loc[available < minimum_indicators, "equity_score"] = np.nan
    frame["equity_percentile"] = frame["equity_score"].rank(pct=True)
    return frame


def build_equity_frame(
    geometry: gpd.GeoDataFrame,
    profiles: Mapping[str, Mapping[str, float]],
    *,
    dguid_column: str = "DGUID",
    reference: Iterable[str] | None = None,
    minimum_indicators: int = 3,
) -> gpd.GeoDataFrame:
    """Join Census equity values to dissemination-area polygons.

    Parameters
    ----------
    geometry : geopandas.GeoDataFrame
        Dissemination-area polygons.
    profiles : mapping
        Indicator name to dissemination-area values.
    dguid_column : str
        Column containing the 2021 dissemination geography ID.
    reference : iterable of str or None
        IDs used for percentile ranks.
    minimum_indicators : int
        Minimum number of need indicators required for a score.

    Returns
    -------
    geopandas.GeoDataFrame
        The input geometry with the Census indicators and equity score.

    Raises
    ------
    ValueError
        When the geometry has no matching geography-ID column or no CRS.
    """
    if dguid_column not in geometry.columns:
        raise ValueError(f"geometry has no {dguid_column} column")
    if geometry.crs is None:
        raise ValueError("equity geometry has no CRS")
    table = combine_profiles(
        profiles,
        reference=reference,
        minimum_indicators=minimum_indicators,
    )
    frame = geometry.copy()
    frame[dguid_column] = frame[dguid_column].astype(str)
    joined = frame.merge(
        table,
        left_on=dguid_column,
        right_index=True,
        how="left",
        validate="many_to_one",
    )
    return gpd.GeoDataFrame(joined, geometry=frame.geometry.name, crs=frame.crs)


def equity_summary(frame: gpd.GeoDataFrame) -> dict[str, object]:
    """Summarise an equity frame for a JSON product.

    Parameters
    ----------
    frame : geopandas.GeoDataFrame
        Output of :func:`build_equity_frame`.

    Returns
    -------
    dict
        Population, area count, score range, and method evidence.
    """
    valid = frame.loc[frame["equity_score"].notna()]
    return {
        "areas": len(frame),
        "areas_with_score": len(valid),
        "population": float(valid["population"].fillna(0.0).sum()),
        "equity_score_min": float(valid["equity_score"].min()) if not valid.empty else None,
        "equity_score_median": (float(valid["equity_score"].median()) if not valid.empty else None),
        "equity_score_max": float(valid["equity_score"].max()) if not valid.empty else None,
        "indicators": list(NEED_INDICATORS),
        "evidence": CENSUS_EVIDENCE.to_dict(),
    }


__all__ = [
    "CENSUS_EVIDENCE",
    "NEED_INDICATORS",
    "PROFILE_SPECS",
    "build_equity_frame",
    "combine_profiles",
    "equity_summary",
    "load_profiles",
    "read_profile_csv",
]
