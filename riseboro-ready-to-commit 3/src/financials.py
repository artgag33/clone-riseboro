"""
src/financials.py
-----------------
Data processing and aggregation engine for the RiseBoro Financials Dashboard.
Handles loading, cleaning, and synthesizing:
  - Unit Rents & Rent Roll (data/units_rents.csv)
  - Capital Development & LIHTC Stacks (data/building_codes.csv)
  - Renovations & Vintage Timeline (data/renovations.csv)
  - Work Order Maintenance OpEx Drag (session_state.wo_df)
"""

import os
import re
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import streamlit as st

from src.sources import hpd_charges

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
UNITS_RENTS_PATH = os.path.join(DATA_DIR, "units_rents.csv")
BUILDING_CODES_PATH = os.path.join(DATA_DIR, "building_codes.csv")
RENOVATIONS_PATH = os.path.join(DATA_DIR, "renovations.csv")

# Known alias mappings for YARDI property codes
PROPERTY_ALIASES = {
    "alliance": "Bushwick Alliance",
    "gdwnpl2": "Goodwin Plaza Phase II",
    "cfbn2": "Central & Flushing / Bushwick North",
    "grovegar": "Grove Gardens",
    "rbha": "RiseBoro Housing Alliance",
    "wb203k": "West Bushwick 203K",
    "baisley": "Baisley Pond Residences",
    "sumner": "Atrium at Sumner",
    "hillsid": "Hillside 1 & 2",
    "326rock": "326 Rockaway",
    "1601dek": "1601 DeKalb",
    "bethany": "Bethany Senior Terraces",
    "rheing": "Rheingold Gardens",
    "gtsplaza": "Gates Plaza",
    "woodlawn": "Woodlawn Senior Living",
    "420stock": "420 Stockholm",
    "sun203k": "Sunset 203K",
    "640broad": "640 Broadway",
    "857hart": "857 Hart Street",
    "924hart": "924 Hart Street",
}


def clean_currency(val: Any) -> float:
    """Parse currency strings like '$1,250.00', '(500)', ' 1200 ' into float."""
    if pd.isna(val) or val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val) if not np.isnan(val) else 0.0

    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "tbd", "n/a", "-", ""):
        return 0.0

    # Negative parenthesized notation like ($500)
    is_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1]

    # Remove $, commas, spaces
    s = re.sub(r"[^\d.]", "", s)
    try:
        num = float(s)
        return -num if is_negative else num
    except ValueError:
        return 0.0


@st.cache_data(show_spinner=False)
def load_units_rents() -> pd.DataFrame:
    """Load and clean units_rents.csv joined with building metadata."""
    if not os.path.exists(UNITS_RENTS_PATH):
        return pd.DataFrame()

    df = pd.read_csv(UNITS_RENTS_PATH, low_memory=False)
    df.columns = df.columns.str.strip()

    # Clean rent
    df["Rent_num"] = df["Rent"].apply(clean_currency)
    df["Bedrooms"] = pd.to_numeric(df["Bedrooms"], errors="coerce").fillna(0).astype(int)
    df["Property_clean"] = df["Property"].astype(str).str.strip().str.lower()
    df["Unit"] = df["Unit"].astype(str).str.strip()
    df["Unit Type"] = df["Unit Type"].astype(str).str.strip()

    # Bedroom Label
    bedroom_map = {0: "Studio (0BR)", 1: "1 Bedroom", 2: "2 Bedroom", 3: "3 Bedroom", 4: "4+ Bedroom"}
    df["Bedroom_Label"] = df["Bedrooms"].map(lambda b: bedroom_map.get(b, f"{b} Bedroom"))

    # Rent Tier
    def _assign_tier(rent: float) -> str:
        if rent <= 0:
            return "Subsidized / $0"
        elif rent < 500:
            return "< $500"
        elif rent < 1000:
            return "$500 – $999"
        elif rent < 1500:
            return "$1,000 – $1,499"
        elif rent < 2000:
            return "$1,500 – $1,999"
        elif rent < 2500:
            return "$2,000 – $2,499"
        else:
            return "$2,500+"

    df["Rent_Tier"] = df["Rent_num"].apply(_assign_tier)

    # Date Available
    df["Date Available"] = pd.to_datetime(df["Date Available"], errors="coerce")
    df["Is_Available"] = df["Date Available"].notna()

    # Load building codes metadata for join
    bc_meta = _load_building_metadata()
    df = df.merge(bc_meta, left_on="Property_clean", right_on="_yardi_key", how="left")

    # Fallback display name for properties
    df["Display_Property"] = df["PROJECT_NAME"].fillna(
        df["PLACE_NAME"].fillna(
            df["Property_clean"].map(PROPERTY_ALIASES).fillna(df["Property"].astype(str).str.upper())
        )
    )
    df["Display_Borough"] = df["Borough"].fillna("Brooklyn")
    df["Display_Housing_Type"] = df["Housing_Type"].fillna("Multi-Family")

    return df


@st.cache_data(show_spinner=False)
def _load_building_metadata() -> pd.DataFrame:
    """Internal helper to load deduplicated building metadata."""
    if not os.path.exists(BUILDING_CODES_PATH):
        return pd.DataFrame(columns=["_yardi_key", "PLACE_NAME", "PROJECT_NAME", "ADDRESS", "Borough", "Housing_Type", "Status"])

    bc = pd.read_csv(BUILDING_CODES_PATH, low_memory=False)
    bc.columns = bc.columns.str.strip()

    bc["_yardi_key"] = (
        bc["YARDI Property Code_2"]
        .astype(str)
        .str.strip()
        .str.lstrip(".")
        .str.lower()
    )

    keep_cols = ["_yardi_key", "PLACE_NAME", "PROJECT_NAME", "ADDRESS", "Borough", "Housing_Type", "Status", "TOTALUNITS"]
    existing_cols = [c for c in keep_cols if c in bc.columns]
    return bc[existing_cols].drop_duplicates(subset=["_yardi_key"])


@st.cache_data(show_spinner=False)
def load_building_financials() -> pd.DataFrame:
    """Load and parse capital development, LIHTC, lender, and commercial fields from building_codes.csv."""
    if not os.path.exists(BUILDING_CODES_PATH):
        return pd.DataFrame()

    bc = pd.read_csv(BUILDING_CODES_PATH, low_memory=False)
    bc.columns = bc.columns.str.strip()

    bc["_yardi_key"] = (
        bc["YARDI Property Code_2"]
        .astype(str)
        .str.strip()
        .str.lstrip(".")
        .str.lower()
    )

    # Clean numeric development & construction costs
    bc["TDC"] = bc["Total Development Cost_PROJECT_2"].apply(clean_currency)
    bc["Construction_Cost"] = bc["Total Construction Cost_PROJECT_2"].apply(clean_currency)
    bc["Total_Units"] = pd.to_numeric(bc["TOTALUNITS"], errors="coerce").fillna(0).astype(int)

    # Cost per unit
    bc["Cost_Per_Unit"] = np.where(bc["Total_Units"] > 0, bc["TDC"] / bc["Total_Units"], 0.0)

    # Clean ownership %
    def _parse_pct(v: Any) -> float:
        if pd.isna(v):
            return 0.0
        s = str(v).replace("%", "").strip()
        try:
            val = float(s)
            return val if val <= 1.0 else val / 100.0
        except ValueError:
            return 0.0

    bc["Ownership_Pct"] = bc["Ownership %_2"].apply(_parse_pct)

    # Clean commercial sqft
    bc["Commercial_SqFt"] = bc["Comm SqFt Leased_commercial"].apply(clean_currency)
    bc["Has_Commercial"] = bc["Commercial Unit"].notna() | (bc["Commercial_SqFt"] > 0)

    # Tax Credit / Subsidy Category
    def _clean_subsidy(row: pd.Series) -> str:
        tc = str(row.get("Tax Credit_2", "")).strip()
        hs = str(row.get("Housing_Services", "")).strip()
        sec8 = str(row.get("Section 8 Type", "")).strip()
        if "4%" in tc or "4% LIHTC" in tc:
            return "4% LIHTC"
        elif "9%" in tc or "9% LIHTC" in tc:
            return "9% LIHTC"
        elif "ESSHI" in hs or "ESSHI" in str(row.get("Program Contact_2", "")):
            return "ESSHI Supportive"
        elif "15/15" in hs:
            return "NYC 15/15 Supportive"
        elif sec8 and sec8.lower() not in ("nan", "none", ""):
            return f"Section 8 ({sec8})"
        elif tc and tc.lower() not in ("nan", "none", "tbd", ""):
            return tc
        return "Standard / Unrestricted"

    bc["Subsidy_Category"] = bc.apply(_clean_subsidy, axis=1)

    # Permanent Lender & Syndicator cleaning
    bc["Lender"] = bc["Public or Private Perm Lender_2"].fillna("Not Specified").astype(str).str.strip()
    bc["Lender"] = bc["Lender"].replace({"nan": "Not Specified", "TBD": "TBD / In Structuring", "None": "None / Direct Equity"})

    bc["Syndicator"] = bc["LIHTC Syndicator_2"].fillna("Not Specified").astype(str).str.strip()
    bc["Syndicator"] = bc["Syndicator"].replace({"nan": "Not Specified", "TBD": "TBD / In Structuring", "None": "Direct / Internal"})

    return bc


@st.cache_data(show_spinner=False)
def load_renovations() -> pd.DataFrame:
    """Load renovations and capital vintage timeline."""
    if not os.path.exists(RENOVATIONS_PATH):
        return pd.DataFrame()

    ren = pd.read_csv(RENOVATIONS_PATH, low_memory=False)
    ren.columns = ren.columns.str.strip()

    ren["Year_Built"] = pd.to_numeric(ren["YEARBUILT_properties"], errors="coerce")
    ren["Most_Recent_Rehab"] = pd.to_numeric(ren["Most recent rehab"], errors="coerce")
    ren["Completion_Date"] = pd.to_datetime(ren["Construction Completion Date_2"], errors="coerce")
    return ren


def calculate_portfolio_kpis(ur_df: pd.DataFrame, bc_df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate executive-level KPI metrics for the portfolio."""
    monthly_gpr = ur_df["Rent_num"].sum() if not ur_df.empty else 0.0
    annual_gpr = monthly_gpr * 12.0
    total_units = len(ur_df) if not ur_df.empty else 0
    active_paying_units = (ur_df["Rent_num"] > 0).sum() if not ur_df.empty else 0
    subsidized_zero_units = total_units - active_paying_units

    avg_rent_paying = ur_df[ur_df["Rent_num"] > 0]["Rent_num"].mean() if active_paying_units > 0 else 0.0
    median_rent = ur_df[ur_df["Rent_num"] > 0]["Rent_num"].median() if active_paying_units > 0 else 0.0

    # Capital Development KPIs
    unique_projects = bc_df.drop_duplicates(subset=["PROJECT_NAME"]) if not bc_df.empty else pd.DataFrame()
    total_tdc = unique_projects["TDC"].sum() if not unique_projects.empty else 0.0
    total_const_cost = unique_projects["Construction_Cost"].sum() if not unique_projects.empty else 0.0
    total_comm_sqft = bc_df["Commercial_SqFt"].sum() if not bc_df.empty else 0.0

    return {
        "monthly_gpr": monthly_gpr,
        "annual_gpr": annual_gpr,
        "total_units": total_units,
        "active_paying_units": active_paying_units,
        "subsidized_zero_units": subsidized_zero_units,
        "avg_rent_paying": avg_rent_paying,
        "median_rent": median_rent,
        "total_tdc": total_tdc,
        "total_const_cost": total_const_cost,
        "total_comm_sqft": total_comm_sqft,
        "property_count": ur_df["Property_clean"].nunique() if not ur_df.empty else 0,
    }


def get_rent_tier_distribution(ur_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate frequency and aggregate rent by rent band."""
    if ur_df.empty:
        return pd.DataFrame()

    tier_order = [
        "Subsidized / $0",
        "< $500",
        "$500 – $999",
        "$1,000 – $1,499",
        "$1,500 – $1,999",
        "$2,000 – $2,499",
        "$2,500+",
    ]

    tier_counts = ur_df.groupby("Rent_Tier", observed=False).agg(
        unit_count=("Unit", "count"),
        total_monthly_rent=("Rent_num", "sum"),
        avg_rent=("Rent_num", "mean"),
    ).reindex(tier_order).fillna(0)

    tier_counts["pct_of_units"] = (tier_counts["unit_count"] / len(ur_df)) * 100.0
    return tier_counts.reset_index()


def get_bedroom_rent_summary(ur_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate rent statistics by bedroom count."""
    if ur_df.empty:
        return pd.DataFrame()

    paying_df = ur_df[ur_df["Rent_num"] > 0]
    summary = paying_df.groupby(["Bedrooms", "Bedroom_Label"]).agg(
        unit_count=("Unit", "count"),
        total_monthly_rent=("Rent_num", "sum"),
        avg_rent=("Rent_num", "mean"),
        median_rent=("Rent_num", "median"),
        min_rent=("Rent_num", "min"),
        max_rent=("Rent_num", "max"),
    ).reset_index().sort_values("Bedrooms")

    return summary


def get_property_revenue_summary(ur_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate revenue economics per property."""
    if ur_df.empty:
        return pd.DataFrame()

    prop_summary = ur_df.groupby(["Property_clean", "Display_Property", "Display_Borough"]).agg(
        total_units=("Unit", "count"),
        paying_units=("Rent_num", lambda s: (s > 0).sum()),
        zero_rent_units=("Rent_num", lambda s: (s <= 0).sum()),
        monthly_rent_roll=("Rent_num", "sum"),
        avg_rent_paying=("Rent_num", lambda s: s[s > 0].mean() if (s > 0).any() else 0.0),
        median_rent=("Rent_num", lambda s: s[s > 0].median() if (s > 0).any() else 0.0),
    ).reset_index()

    prop_summary["annual_rent_roll"] = prop_summary["monthly_rent_roll"] * 12.0
    prop_summary = prop_summary.sort_values("monthly_rent_roll", ascending=False)
    return prop_summary


def calculate_maintenance_drag(
    wo_df: pd.DataFrame,
    ur_df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Calculate Maintenance OpEx Drag:
    Compare work order repair expenditures against Gross Potential Rent per property and trade.
    """
    if wo_df is None or wo_df.empty:
        return pd.DataFrame(), pd.DataFrame(), {}

    wo = wo_df.copy()

    # Clean WO Total
    if "Total" in wo.columns:
        wo["WO_Cost"] = wo["Total"].apply(clean_currency)
    elif "Unit Price" in wo.columns and "Quantity" in wo.columns:
        wo["WO_Cost"] = wo["Unit Price"].apply(clean_currency) * pd.to_numeric(wo["Quantity"], errors="coerce").fillna(1)
    else:
        wo["WO_Cost"] = 0.0

    wo["Building_clean"] = wo["Building"].astype(str).str.strip().str.lower()

    # Time span of work orders for annualization
    date_col = "Call Date" if "Call Date" in wo.columns else ("Start Date" if "Start Date" in wo.columns else None)
    years_span = 1.0
    if date_col and pd.api.types.is_datetime64_any_dtype(wo[date_col]):
        min_date = wo[date_col].min()
        max_date = wo[date_col].max()
        if pd.notna(min_date) and pd.notna(max_date):
            days = (max_date - min_date).days
            if days > 30:
                years_span = max(days / 365.25, 0.25)

    # 1. Maintenance by Property
    wo_prop = wo.groupby("Building_clean").agg(
        wo_count=("WO" if "WO" in wo.columns else "Building", "count"),
        total_wo_spend=("WO_Cost", "sum"),
    ).reset_index()
    wo_prop["annualized_wo_spend"] = wo_prop["total_wo_spend"] / years_span

    # Merge with Rent Summary
    prop_rent = get_property_revenue_summary(ur_df)
    drag_df = prop_rent.merge(wo_prop, left_on="Property_clean", right_on="Building_clean", how="left")
    drag_df["wo_count"] = drag_df["wo_count"].fillna(0).astype(int)
    drag_df["total_wo_spend"] = drag_df["total_wo_spend"].fillna(0.0)
    drag_df["annualized_wo_spend"] = drag_df["annualized_wo_spend"].fillna(0.0)

    # Maintenance Drag % = Annualized WO spend / Annual Rent Roll
    drag_df["maintenance_drag_pct"] = np.where(
        drag_df["annual_rent_roll"] > 0,
        (drag_df["annualized_wo_spend"] / drag_df["annual_rent_roll"]) * 100.0,
        0.0,
    )
    drag_df["wo_spend_per_unit"] = np.where(
        drag_df["total_units"] > 0,
        drag_df["annualized_wo_spend"] / drag_df["total_units"],
        0.0,
    )

    drag_df = drag_df.sort_values("maintenance_drag_pct", ascending=False)

    # 2. Maintenance by Trade / Category
    cat_col = "issue_category" if "issue_category" in wo.columns else "Brief Desc"
    wo_cat = wo.groupby(cat_col).agg(
        wo_count=("WO_Cost", "count"),
        total_spend=("WO_Cost", "sum"),
        avg_cost_per_wo=("WO_Cost", "mean"),
    ).reset_index().sort_values("total_spend", ascending=False)
    wo_cat["pct_of_total_spend"] = (wo_cat["total_spend"] / max(wo_cat["total_spend"].sum(), 1.0)) * 100.0

    # 3. Overall Portfolio OpEx KPI
    total_spend = wo["WO_Cost"].sum()
    total_ann_spend = total_spend / years_span
    total_ann_rent = prop_rent["annual_rent_roll"].sum() if not prop_rent.empty else 1.0
    portfolio_drag = (total_ann_spend / max(total_ann_rent, 1.0)) * 100.0

    kpis = {
        "total_wo_spend": total_spend,
        "annualized_wo_spend": total_ann_spend,
        "portfolio_maintenance_drag_pct": portfolio_drag,
        "avg_cost_per_wo": wo[wo["WO_Cost"] > 0]["WO_Cost"].mean() if (wo["WO_Cost"] > 0).any() else 0.0,
        "total_wos_costed": len(wo),
        "years_span": years_span,
    }

    return drag_df, wo_cat, kpis


# ── Standard NYC HPD Statutory Fee Schedule ───────────────────────────────────
HPD_FEE_SCHEDULE: dict[str, float] = {
    "INSPECTION FEE": 200.0,
    "Hot Water Inspection Fee": 200.0,
    "Heat Inspection Fee": 200.0,
    "AEP Complaint Inspection Fee": 200.0,
    "Initial Re-inspection Fee": 200.0,
    "Six Month Program Fee": 1000.0,
    "False Certification Fee": 500.0,
}


@st.cache_data(show_spinner=False, ttl=3600)
def load_portfolio_hpd_charges(renovations_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    Fetch and clean NYC HPD Fee Charges (dataset cp6j-7bjj) for all building addresses in renovations.csv.
    Batches SoQL address queries to NYC Open Data and maps to RiseBoro projects and borough data.
    """
    from src.sources import hpd_charges

    if renovations_df is None or renovations_df.empty:
        renovations_df = load_renovations()

    if renovations_df.empty:
        return pd.DataFrame()

    # Build address filter clauses from renovations.csv
    addr_clauses: list[str] = []
    addr_proj_map: dict[tuple[str, str], tuple[str, str, str]] = {}

    for _, row in renovations_df.iterrows():
        project = str(row.get("PROJECT_NAME", "")).strip()
        raw_addr = str(row.get("ADDRESS", "")).strip()
        if not raw_addr or raw_addr.lower() in ("nan", "none", ""):
            continue

        h, s, b = hpd_charges.parse_address(raw_addr)
        if not h or not s:
            continue
        boro = b or "BROOKLYN"

        house_nums = [h]
        if "-" in h:
            parts = h.split("-")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                p1, p2 = int(parts[0]), int(parts[1])
                if p2 - p1 <= 10:
                    house_nums = [str(n) for n in range(p1, p2 + 1, 2)]
                else:
                    house_nums = [parts[0], parts[1], h]
            else:
                house_nums = [h]

        for house_num in house_nums:
            safe_street = s.replace("'", "''")
            clause = f"(housenumber = '{house_num}' AND upper(streetname) like '{safe_street}%')"
            addr_clauses.append(clause)
            addr_proj_map[(house_num, s)] = (project, raw_addr, boro)

    if not addr_clauses:
        return pd.DataFrame()

    # Query Socrata in chunks with OR
    chunk_size = 25
    all_frames: list[pd.DataFrame] = []

    for i in range(0, len(addr_clauses), chunk_size):
        chunk = addr_clauses[i : i + chunk_size]
        or_where = " OR ".join(chunk)
        try:
            chunk_df = hpd_charges.fetch(where=or_where, limit=5000)
            if not chunk_df.empty:
                all_frames.append(chunk_df)
        except Exception:
            continue

    if not all_frames:
        return pd.DataFrame()

    charges = pd.concat(all_frames, ignore_index=True).drop_duplicates(subset=["feeid"])
    if charges.empty:
        return pd.DataFrame()

    # Standardize types and dates
    charges["bbl"] = charges["bbl"].astype(str).str.strip().str.split(".").str[0]
    charges["bin"] = charges["bin"].astype(str).str.strip().str.split(".").str[0]
    charges["feeissueddate_dt"] = pd.to_datetime(charges["feeissueddate"], errors="coerce")
    charges["doftransferdate_dt"] = pd.to_datetime(charges["doftransferdate"], errors="coerce")
    charges["Transferred_To_DOF"] = charges["doftransferdate_dt"].notna()
    charges["Year_Issued"] = charges["feeissueddate_dt"].dt.year.fillna(0).astype(int)
    charges["Year_Month"] = charges["feeissueddate_dt"].dt.strftime("%Y-%m")

    # Clean text columns
    charges["housenumber"] = charges["housenumber"].fillna("").astype(str).str.strip()
    charges["streetname"] = charges["streetname"].fillna("").astype(str).str.strip()
    charges["Building_Address"] = (charges["housenumber"] + " " + charges["streetname"]).str.title().str.strip()

    charges["Fee_Type"] = charges["feetype"].fillna("Inspection Fee").astype(str).str.strip()
    charges["Source_Type"] = charges["feesourcetype"].fillna("Complaint").astype(str).str.strip()

    # Calculate statutory estimated fee amount
    charges["Estimated_Fee_Amount"] = charges["Fee_Type"].map(
        lambda t: HPD_FEE_SCHEDULE.get(t, 200.0)
    )

    # Map project name and borough from renovations.csv
    def _match_proj(r: pd.Series) -> str:
        h = str(r.get("housenumber", "")).strip()
        s = hpd_charges.normalize_street_name(str(r.get("streetname", "")))
        if (h, s) in addr_proj_map:
            return addr_proj_map[(h, s)][0]
        for (map_h, map_s), (proj, _, _) in addr_proj_map.items():
            if map_h == h and (map_s.startswith(s) or s.startswith(map_s)):
                return proj
        return str(r.get("Building_Address", "Portfolio Property"))

    def _match_raw_addr(r: pd.Series) -> str:
        h = str(r.get("housenumber", "")).strip()
        s = hpd_charges.normalize_street_name(str(r.get("streetname", "")))
        if (h, s) in addr_proj_map:
            return addr_proj_map[(h, s)][1]
        for (map_h, map_s), (_, raw_a, _) in addr_proj_map.items():
            if map_h == h and (map_s.startswith(s) or s.startswith(map_s)):
                return raw_a
        return str(r.get("Building_Address", ""))

    charges["PROJECT_NAME"] = charges.apply(_match_proj, axis=1)
    charges["Matched_Address"] = charges.apply(_match_raw_addr, axis=1)
    charges["Display_Property"] = charges["PROJECT_NAME"]
    charges["Display_Borough"] = charges["boro"].fillna("BROOKLYN").astype(str).str.title()

    return charges


def calculate_hpd_fee_kpis(
    charges_df: pd.DataFrame,
    building_df: Optional[pd.DataFrame] = None,
) -> dict[str, Any]:
    """Calculate executive KPI metrics for portfolio HPD fee charges."""
    if charges_df.empty:
        return {
            "total_charges": 0,
            "total_fee_amount": 0.0,
            "affected_properties": 0,
            "dof_transferred_count": 0,
            "dof_transfer_pct": 0.0,
            "top_fee_type": "None",
            "latest_fee_date": "N/A",
        }

    total_charges = len(charges_df)
    total_fee_amount = charges_df["Estimated_Fee_Amount"].sum()
    affected_properties = charges_df["Display_Property"].nunique()
    dof_transferred_count = int(charges_df["Transferred_To_DOF"].sum())
    dof_transfer_pct = (dof_transferred_count / max(total_charges, 1)) * 100.0

    top_fee_mode = charges_df["Fee_Type"].mode()
    top_fee_type = str(top_fee_mode.iloc[0]) if not top_fee_mode.empty else "Inspection Fee"

    latest_date_dt = charges_df["feeissueddate_dt"].max()
    latest_fee_date = latest_date_dt.strftime("%b %d, %Y") if pd.notna(latest_date_dt) else "N/A"

    return {
        "total_charges": total_charges,
        "total_fee_amount": total_fee_amount,
        "affected_properties": affected_properties,
        "dof_transferred_count": dof_transferred_count,
        "dof_transfer_pct": dof_transfer_pct,
        "top_fee_type": top_fee_type,
        "latest_fee_date": latest_fee_date,
    }


def get_building_fee_summary(charges_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate HPD fee charges per building and project."""
    if charges_df.empty:
        return pd.DataFrame()

    def _get_top_infraction(series: pd.Series) -> str:
        mode_val = series.mode()
        return str(mode_val.iloc[0]) if not mode_val.empty else "N/A"

    summary = (
        charges_df.groupby(["Display_Property", "Building_Address", "bbl", "Display_Borough"], observed=False)
        .agg(
            total_charges=("feeid", "count"),
            total_fee_liability=("Estimated_Fee_Amount", "sum"),
            dof_transferred=("Transferred_To_DOF", "sum"),
            latest_fee_date=("feeissueddate_dt", "max"),
            top_infraction=("Fee_Type", _get_top_infraction),
        )
        .reset_index()
    )

    summary["dof_transfer_pct"] = (
        summary["dof_transferred"] / summary["total_charges"].replace(0, 1)
    ) * 100.0
    summary = summary.sort_values(["total_charges", "total_fee_liability"], ascending=[False, False])
    return summary


def get_fee_type_distribution(charges_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate frequency, percentage, and liability by fee infraction type."""
    if charges_df.empty:
        return pd.DataFrame()

    dist = (
        charges_df.groupby("Fee_Type", observed=False)
        .agg(
            charge_count=("feeid", "count"),
            total_fee_liability=("Estimated_Fee_Amount", "sum"),
            avg_fee=("Estimated_Fee_Amount", "mean"),
        )
        .reset_index()
        .sort_values("charge_count", ascending=False)
    )

    dist["pct_of_total"] = (dist["charge_count"] / max(len(charges_df), 1)) * 100.0
    return dist


def get_annual_fee_trend(charges_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate annual fee charge volume and liability."""
    if charges_df.empty:
        return pd.DataFrame()

    valid_years = charges_df[charges_df["Year_Issued"] > 2000].copy()
    if valid_years.empty:
        return pd.DataFrame()

    trend = (
        valid_years.groupby("Year_Issued", observed=False)
        .agg(
            charge_count=("feeid", "count"),
            total_fee_liability=("Estimated_Fee_Amount", "sum"),
            dof_transferred=("Transferred_To_DOF", "sum"),
        )
        .reset_index()
        .sort_values("Year_Issued")
    )
    return trend


def get_fee_source_distribution(charges_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate distribution of source documents (Complaint, Violation, Route for Inspection, etc.)."""
    if charges_df.empty:
        return pd.DataFrame()

    sources = (
        charges_df.groupby("Source_Type", observed=False)
        .agg(
            charge_count=("feeid", "count"),
            total_fee_liability=("Estimated_Fee_Amount", "sum"),
        )
        .reset_index()
        .sort_values("charge_count", ascending=False)
    )
    return sources

