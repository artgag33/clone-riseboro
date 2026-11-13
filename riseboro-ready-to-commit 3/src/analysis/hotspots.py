"""
hotspots.py — unit-level work-order volume analysis.

Identifies apartments generating disproportionate work-order volume and compares
their issue mix against the portfolio as a whole. Extracted from week3.py, where
the statistics, the console output, and the Markdown writing shared one function.
"""

from __future__ import annotations

import pandas as pd

# Property-wide rollup codes that appear in prop_unit but are not apartments.
NON_APARTMENT_CODES = ["wb203k", "rheing", "gtsplaza"]

# Common areas and non-residential spaces, matched case-insensitively.
NON_APARTMENT_PATTERN = "COMM|COMMERCIAL|BOILER|COMMON|OFFICE|SUPER|EXTERIOR|BUILDING|^BLDG$"

# Categories profiled when comparing hotspot groups against the portfolio.
PROFILE_CATEGORIES = [
    "Plumbing",
    "Extermination",
    "Appliances",
    "Doors and Locks",
    "Electrical",
    "Painting and Plastering",
]


def exclude_non_apartments(df: pd.DataFrame) -> pd.DataFrame:
    """Drop property-wide rollups and common-area records, keeping apartments only."""
    df = df.dropna(subset=["prop_unit"])
    df = df[~df["prop_unit"].isin(NON_APARTMENT_CODES)]
    return df[
        ~df["prop_unit"].str.contains(NON_APARTMENT_PATTERN, case=False, na=False)
    ]


def unit_volume(df: pd.DataFrame) -> pd.Series:
    """Work-order count per unit, descending."""
    return df["prop_unit"].value_counts()


def top_unit_index(
    df: pd.DataFrame, *, fraction: float | None = None, count: int | None = None
):
    """
    Index of the highest-volume units, selected by fraction of all units or a fixed count.

    Exactly one of fraction or count must be given.
    """
    if (fraction is None) == (count is None):
        raise ValueError("pass exactly one of fraction= or count=")
    counts = unit_volume(df)
    n = max(1, int(len(counts) * fraction)) if fraction is not None else count
    return counts.head(n).index


def group_stats(df: pd.DataFrame, categories: list[str] | None = None) -> dict:
    """Volume, resolution time, and category mix for one group of units."""
    categories = categories if categories is not None else PROFILE_CATEGORIES
    units = df["prop_unit"].nunique()
    stats = {
        "Units": units,
        "Avg WOs/Unit": len(df) / units,
        "Avg Resolution (Days)": df["ttl_days"].mean(),
    }
    for cat in categories:
        stats[f"{cat} %"] = (df["final_category"] == cat).mean() * 100
    return stats


def compare_groups(
    df: pd.DataFrame, categories: list[str] | None = None
) -> pd.DataFrame:
    """Portfolio vs top-10% vs top-10 units, one row per group."""
    top_pct = df[df["prop_unit"].isin(top_unit_index(df, fraction=0.10))]
    top_ten = df[df["prop_unit"].isin(top_unit_index(df, count=10))]
    return pd.DataFrame(
        {
            "All Units": group_stats(df, categories),
            "Top 10% Units": group_stats(top_pct, categories),
            "Top 10 Units": group_stats(top_ten, categories),
        }
    ).T


def top_units_detail(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Per-unit detail for the n highest-volume units, including their dominant issue."""
    units = top_unit_index(df, count=n)
    rows = []
    for unit in units:
        unit_wos = df[df["prop_unit"] == unit]
        category_share = unit_wos["final_category"].value_counts(normalize=True)
        top_cat = category_share.index[0]
        rows.append(
            {
                "Property": unit_wos["property_name"].iloc[0],
                "Total WOs": len(unit_wos),
                "Avg Resolution (Days)": unit_wos["ttl_days"].mean(),
                "Primary Issue (Share %)": f"{top_cat} ({category_share.iloc[0] * 100:.1f}%)",
            }
        )
    detail = pd.DataFrame(rows, index=units)
    detail.index.name = "Unit"
    return detail
