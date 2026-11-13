"""
src/analysis/adapter.py
-----------------------
Adapter layer that normalizes Streamlit dashboard work-order data into the schema
expected by the src/analysis helper modules (trends.py, hotspots.py, significance.py).
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from src.config import MONTH_MAP, MONTH_NAMES


def adapt_for_analysis(df: pd.DataFrame, building_info: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Transform dashboard DataFrame into the standardized schema for analysis modules:
      - source_property (from Building)
      - property_name (from bc_PROJECT_NAME or PLACE_NAME or Building)
      - prop_unit (from Prop-Unit)
      - final_category (from issue_category / Brief Desc)
      - call_date (from Call Date)
      - status (from Status)
      - description (from Brief Desc)
      - ttl_days (from Start Date - Call Date, clipped [0, 365])
      - Year, Month_Num, Month (derived from call_date)
    """
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()

    # Column mappings
    rename_map = {}
    if "Building" in out.columns:
        rename_map["Building"] = "source_property"
    if "Prop-Unit" in out.columns:
        rename_map["Prop-Unit"] = "prop_unit"
    if "issue_category" in out.columns:
        rename_map["issue_category"] = "final_category"
    if "Call Date" in out.columns:
        rename_map["Call Date"] = "call_date"
    if "Status" in out.columns:
        rename_map["Status"] = "status"
    if "Brief Desc" in out.columns:
        rename_map["Brief Desc"] = "description"

    out = out.rename(columns=rename_map)

    # Ensure required columns exist
    if "source_property" not in out.columns:
        out["source_property"] = "Unknown"
    if "prop_unit" not in out.columns:
        out["prop_unit"] = "Unknown"
    if "final_category" not in out.columns:
        out["final_category"] = "Other"

    # Derive property_name for display
    if "bc_PROJECT_NAME" in out.columns and out["bc_PROJECT_NAME"].notna().any():
        out["property_name"] = out["bc_PROJECT_NAME"].fillna(out["source_property"])
    elif "bc_PLACE_NAME" in out.columns and out["bc_PLACE_NAME"].notna().any():
        out["property_name"] = out["bc_PLACE_NAME"].fillna(out["source_property"])
    else:
        out["property_name"] = out["source_property"]

    # Normalize Dates and add Year, Month_Num, Month
    if "call_date" in out.columns:
        out["call_date"] = pd.to_datetime(out["call_date"], errors="coerce")
        out["Year"] = out["call_date"].dt.year.astype("Int64")
        out["Month_Num"] = out["call_date"].dt.month
        out["Month"] = out["Month_Num"]  # significance.seasonality expects 'Month'
    else:
        out["call_date"] = pd.NaT
        out["Year"] = pd.Series(dtype="Int64")
        out["Month_Num"] = pd.Series(dtype="float")
        out["Month"] = pd.Series(dtype="float")

    # Compute resolution duration in days (ttl_days)
    # Search for completion / close / start date columns
    date_candidates = [
        "Completion Date", "Completed Date", "Close Date", "Closed Date",
        "Date Completed", "Finish Date", "End Date", "Resolution Date",
        "Start Date", "start_date"
    ]
    end_col = None
    for cand in date_candidates:
        if cand in out.columns and out[cand].notna().any():
            end_col = cand
            break

    if end_col and "call_date" in out.columns:
        end_dates = pd.to_datetime(out[end_col], errors="coerce")
        # Compute difference in days
        diff_days = (end_dates - out["call_date"]).dt.total_seconds() / 86400.0
        
        # Filter invalid / erroneous values:
        # If end_date is before call_date by more than 1 day, it's an erroneous timestamp (set to NaN)
        diff_days = diff_days.mask(diff_days < -1, np.nan)
        # If slightly negative within same day (-1 <= diff < 0 due to hour/timezone offsets), treat as 0
        diff_days = diff_days.mask((diff_days < 0) & (diff_days >= -1), 0.0)
        # If exceeds a year (365 days), cap at 365 as considered resolved
        diff_days = diff_days.mask(diff_days > 365, 365.0)
        
        out["ttl_days"] = diff_days
    else:
        out["ttl_days"] = np.nan

    return out
