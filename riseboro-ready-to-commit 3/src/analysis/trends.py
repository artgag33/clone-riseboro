"""
trends.py — yearly and seasonal work-order aggregation.

Extracted from week2.py and week2_charts.py, which each carried their own copy
of this logic alongside their own printing and plotting.
"""

from __future__ import annotations

import pandas as pd

try:
    from src.config import MONTH_MAP, MONTH_NAMES
except ImportError:
    from config import MONTH_MAP, MONTH_NAMES


def filter_property(df: pd.DataFrame, prop_code: str) -> pd.DataFrame:
    """Rows for one property, matched case-insensitively on source_property."""
    return df[df["source_property"].astype(str).str.lower() == prop_code.lower()].copy()


def add_time_parts(df: pd.DataFrame) -> pd.DataFrame:
    """Add Year (nullable Int64) and Month_Num columns derived from call_date."""
    df = df.copy()
    df["call_date"] = pd.to_datetime(df["call_date"], errors="coerce")
    df["Year"] = df["call_date"].dt.year.astype("Int64")
    df["Month_Num"] = df["call_date"].dt.month
    return df


def yearly_counts(df: pd.DataFrame, exclude_year: int | None = None) -> pd.Series:
    """Work orders per calendar year, indexed by year."""
    counts = df.groupby("Year").size().rename("Work Orders")
    if exclude_year is not None:
        counts = counts[counts.index != exclude_year]
    return counts


def monthly_counts(df: pd.DataFrame, *, fill_missing: bool = False) -> pd.Series:
    """
    Work orders per calendar month, indexed by month name in calendar order.

    fill_missing=False drops months with no data (the console report's behavior);
    fill_missing=True zero-fills them so all 12 months are present, which is what
    the charts need for a stable x-axis.
    """
    counts = df.groupby("Month_Num").size().rename("Work Orders")
    if fill_missing:
        counts = counts.reindex(range(1, 13)).fillna(0)
        counts.index = counts.index.map(MONTH_MAP)
        return counts
    counts.index = counts.index.map(MONTH_MAP)
    return counts.reindex(MONTH_NAMES).dropna().astype(int)


def monthly_average_per_year(df: pd.DataFrame) -> pd.Series:
    """Average work orders per month across all years present, zero-filled to 12 months."""
    totals = monthly_counts(df, fill_missing=True)
    n_years = len(df["Year"].dropna().unique())
    return (totals / n_years).round(1)


def missing_date_count(df: pd.DataFrame) -> int:
    """Rows whose call_date failed to parse."""
    return int(df["call_date"].isna().sum())


def status_breakdown(df: pd.DataFrame) -> pd.Series:
    """Work-order counts by status, including nulls."""
    return df["status"].value_counts(dropna=False)
