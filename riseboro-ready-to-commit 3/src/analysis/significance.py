"""
significance.py — statistical tests for the trend findings.

Answers whether the patterns visible in the trend charts are real: a linear
regression over yearly counts for long-term direction, and a chi-square
goodness-of-fit test against a uniform distribution for seasonality.

Extracted from scratch/statistical_tests.py.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


@dataclass(frozen=True)
class TrendResult:
    """Linear fit over yearly work-order counts."""

    slope: float
    intercept: float
    r_squared: float
    p_value: float
    std_err: float
    n_years: int
    mean_count: float

    @property
    def significant(self) -> bool:
        return self.p_value < 0.05


@dataclass(frozen=True)
class SeasonalityResult:
    """Chi-square goodness-of-fit against a uniform monthly distribution."""

    chi2: float
    p_value: float
    monthly_counts: pd.Series

    @property
    def significant(self) -> bool:
        return self.p_value < 0.05


@dataclass(frozen=True)
class MonthOutlier:
    """A month whose share of work orders differs significantly from 1/12."""

    month: int
    count: int
    proportion: float
    z_stat: float
    p_value: float

    @property
    def direction(self) -> str:
        return "HIGHER" if self.proportion > 1 / 12 else "LOWER"


def yearly_trend(
    df: pd.DataFrame,
    *,
    min_year: int | None = None,
    exclude_year: int | None = 2026,
) -> TrendResult | None:
    """
    Fit a line to work orders per year. Returns None when fewer than 3 years exist.

    exclude_year drops a partial year that would otherwise drag the slope down.
    """
    counts = df.groupby("Year").size().reset_index(name="Count")
    if exclude_year is not None:
        counts = counts[counts["Year"] != exclude_year]
    if min_year is not None:
        counts = counts[counts["Year"] >= min_year]
    if len(counts) <= 2:
        return None

    fit = stats.linregress(counts["Year"], counts["Count"])
    return TrendResult(
        slope=fit.slope,
        intercept=fit.intercept,
        r_squared=fit.rvalue**2,
        p_value=fit.pvalue,
        std_err=fit.stderr,
        n_years=len(counts),
        mean_count=counts["Count"].mean(),
    )


def seasonality(df: pd.DataFrame) -> SeasonalityResult:
    """
    Test whether work orders are uniformly distributed across the twelve months.

    H0: uniform (no seasonality). H1: not uniform (seasonality exists).
    """
    counts = df.groupby("Month").size().reindex(range(1, 13), fill_value=0)
    expected = np.full(12, counts.sum() / 12.0)
    chi2, p_value = stats.chisquare(counts.values, f_exp=expected)
    return SeasonalityResult(chi2=chi2, p_value=p_value, monthly_counts=counts)


def subcategory_trends(df: pd.DataFrame, min_n: int = 30) -> pd.DataFrame:
    """
    Yearly trend and seasonal peak for every (final_category, subcategory_primary)
    pair with at least min_n rows, one row per pair.

    Existing reports test category-level counts only (Plumbing overall, not
    which kind of plumbing problem). This is the same two tests — linear
    regression for direction, chi-square + z-test for seasonality — applied
    one level finer, which is where "stock up on flapper valves every April"
    kind of findings actually live. min_n=30 keeps both tests meaningful: the
    yearly regression needs multiple years of non-trivial counts, and the
    monthly chi-square needs enough rows that 12 buckets aren't mostly empty.

    Caller is responsible for excluding placeholder subcategories ("Other",
    "Blank/No Desc", "Address-Only (No Work Desc)") before calling this —
    trending on those isn't informative.
    """
    columns = [
        "final_category",
        "subcategory_primary",
        "n",
        "yearly_slope",
        "yearly_p_value",
        "yearly_significant",
        "seasonal_p_value",
        "seasonal_significant",
        "peak_month",
        "peak_direction",
        "peak_share_pct",
    ]
    rows = []
    for (category, subcat), group in df.groupby(
        ["final_category", "subcategory_primary"]
    ):
        if len(group) < min_n:
            continue
        trend = yearly_trend(group)
        season = seasonality(group)
        peak = max(
            month_outliers(season.monthly_counts),
            key=lambda o: abs(o.z_stat),
            default=None,
        )
        rows.append(
            {
                "final_category": category,
                "subcategory_primary": subcat,
                "n": len(group),
                "yearly_slope": trend.slope if trend else None,
                "yearly_p_value": trend.p_value if trend else None,
                "yearly_significant": trend.significant if trend else False,
                "seasonal_p_value": season.p_value,
                "seasonal_significant": season.significant,
                "peak_month": peak.month if peak else None,
                "peak_direction": peak.direction if peak else None,
                "peak_share_pct": round(peak.proportion * 100, 1) if peak else None,
            }
        )
    if not rows:
        return pd.DataFrame(columns=columns)
    return (
        pd.DataFrame(rows, columns=columns)
        .sort_values(
            ["yearly_significant", "seasonal_significant", "n"], ascending=False
        )
        .reset_index(drop=True)
    )


def month_outliers(
    monthly_counts: pd.Series, alpha: float = 0.05
) -> list[MonthOutlier]:
    """
    Months whose share differs significantly from the uniform 1/12 expectation.

    One-sample z-test for a proportion, per month.
    """
    total = monthly_counts.sum()
    p0 = 1 / 12
    outliers = []
    for month in range(1, 13):
        count = monthly_counts[month]
        proportion = count / total
        z_stat = (proportion - p0) / np.sqrt(p0 * (1 - p0) / total)
        p_value = 2 * (1 - stats.norm.cdf(abs(z_stat)))
        if p_value < alpha:
            outliers.append(
                MonthOutlier(
                    month=month,
                    count=int(count),
                    proportion=proportion,
                    z_stat=z_stat,
                    p_value=p_value,
                )
            )
    return outliers
