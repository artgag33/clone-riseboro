"""
dashboard_pages/home.py
-------------
Riseboro Work-Order Analytics Dashboard
Driven by data uploaded via dashboard_pages/upload.py (session_state.wo_df).
Columns: WO, Prop-Unit, Building, Status, Call Date, Start Date,
         Employee, Brief Desc, Quantity, Stock, Stock Description,
         Unit Price, Total
"""

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.auth import require_page_access

require_page_access()

import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk


from streamlit_echarts import st_echarts
from src.components import metric_card, section_header, divider
from src.helpers import classify_issue, get_season
from src.config import MONTH_MAP
from src.analysis.adapter import adapt_for_analysis
from src.analysis.hotspots import exclude_non_apartments, compare_groups, top_units_detail
from src.analysis.trends import yearly_counts, monthly_counts
from src.analysis.significance import yearly_trend, seasonality, month_outliers

# ── Palette ──────────────────────────────────────────────────────────────────
PRIMARY = "#013494"
PRIMARY_L = "#0252cc"
ACCENT = "#1e88e5"
COLORS = [
    PRIMARY,
    PRIMARY_L,
    ACCENT,
    "#42a5f5",
    "#90caf9",
    "#bbdefb",
    "#e53935",
    "#fb8c00",
    "#43a047",
    "#8e24aa",
]

# ─────────────────────────────────────────────────────────────────────────────
# PAGE STYLE
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }

        .hero-banner {
            background: linear-gradient(120deg, #013494 0%, #0252cc 60%, #1565c0 100%);
            border-radius: 20px;
            padding: 2rem 2.5rem;
            color: white;
            margin-bottom: 1.5rem;
            box-shadow: 0 8px 32px rgba(1,52,148,0.3);
        }
        .hero-banner h1 { margin:0; font-size:1.9rem; font-weight:800; }
        .hero-banner p  { margin:0.4rem 0 0; opacity:.75; font-size:0.95rem; }

        .chart-card {
            background: white;
            border-radius: 16px;
            padding: 1.4rem;
            box-shadow: 0 2px 12px rgba(0,0,0,0.07);
            margin-bottom: 1rem;
        }
        .chart-card-title {
            color: #013494;
            font-weight: 700;
            font-size: 1rem;
            margin-bottom: 0.75rem;
        }

        /* empty state */
        .empty-state {
            background: linear-gradient(135deg, #f0f7ff 0%, #e8f0fe 100%);
            border: 2px dashed #013494;
            border-radius: 20px;
            padding: 3rem 2rem;
            text-align: center;
            color: #013494;
        }
        .empty-state h2 { font-size: 1.4rem; font-weight: 700; margin: 0.5rem 0; }
        .empty-state p  { opacity: 0.7; font-size: 0.95rem; }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #013494 0%, #0a2d6e 100%);
            color: white;
        }
        section[data-testid="stSidebar"] * { color: white; }
        section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.2); }
        section[data-testid="stSidebar"] .schema-pill {color: #013494;}
        section[data-testid="stSidebar"] input {color: #013494;}
        section[data-testid="stSidebar"] code {color: #013494;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# LOAD DATA FROM SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
raw_df: pd.DataFrame | None = st.session_state.get("wo_df", None)
has_data = raw_df is not None and len(raw_df) > 0

if has_data:
    raw_df = raw_df.copy()

    # Rename columns to standard names case-insensitively
    standard_renames = {}
    for col in raw_df.columns:
        col_lower = str(col).lower().strip()
        if col_lower in ("wo", "wo #", "work order"):
            standard_renames[col] = "WO"
        elif col_lower in ("prop-unit", "prop unit", "unit"):
            standard_renames[col] = "Prop-Unit"
        elif col_lower in ("building", "bldg", "building code"):
            standard_renames[col] = "Building"
        elif col_lower in ("status", "state"):
            standard_renames[col] = "Status"
        elif col_lower in ("call date", "call_date", "date"):
            standard_renames[col] = "Call Date"
        elif col_lower in (
            "start date", "start_date", "completion date", "completed date",
            "close date", "closed date", "end date", "date completed", "finish date", "resolution date"
        ):
            standard_renames[col] = "Start Date"
        elif col_lower in ("employee", "emp"):
            standard_renames[col] = "Employee"
        elif col_lower in ("brief desc", "brief_desc", "description", "desc"):
            standard_renames[col] = "Brief Desc"
        elif col_lower in ("quantity", "qty"):
            standard_renames[col] = "Quantity"
        elif col_lower in ("stock", "sku"):
            standard_renames[col] = "Stock"
        elif col_lower in ("stock description", "stock_description"):
            standard_renames[col] = "Stock Description"
        elif col_lower in ("unit price", "unit_price", "price"):
            standard_renames[col] = "Unit Price"
        elif col_lower in ("total", "amount"):
            standard_renames[col] = "Total"
        elif col_lower in ("issue_category", "issue category", "subcategory", "subcat"):
            standard_renames[col] = "issue_category"
        elif col_lower in ("season", "seasons"):
            standard_renames[col] = "season"

    if standard_renames:
        raw_df = raw_df.rename(columns=standard_renames)

    # Populate issue_category if missing
    if "issue_category" not in raw_df.columns:
        if "Brief Desc" in raw_df.columns:
            raw_df["issue_category"] = raw_df["Brief Desc"].apply(classify_issue)
        else:
            raw_df["issue_category"] = pd.NA

    # Populate season if missing
    if "season" not in raw_df.columns:
        if "Call Date" in raw_df.columns:
            if not pd.api.types.is_datetime64_any_dtype(raw_df["Call Date"]):
                raw_df["Call Date"] = pd.to_datetime(
                    raw_df["Call Date"], errors="coerce"
                )
            raw_df["season"] = raw_df["Call Date"].apply(get_season)
        else:
            raw_df["season"] = pd.NA


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ️ Dashboard Controls")
    st.markdown("---")

    if has_data:
        # Date range filter on Call Date
        st.markdown("** Filter by Call Date**")
        if "Call Date" in raw_df.columns and raw_df["Call Date"].notna().any():
            min_date = raw_df["Call Date"].min().date()
            max_date = raw_df["Call Date"].max().date()
            date_range = st.date_input(
                "Call date range",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                label_visibility="collapsed",
                key="date_range",
            )
        else:
            date_range = None
            st.caption("No date data available.")

        st.markdown("---")

        # Building filter
        st.markdown("** Filter by Building**")
        buildings = (
            sorted(raw_df["Building"].dropna().unique().tolist())
            if "Building" in raw_df.columns
            else []
        )
        selected_buildings = st.multiselect(
            "Select buildings",
            options=buildings,
            default=buildings,
            label_visibility="collapsed",
            key="bldg_filter",
        )

        st.markdown("---")

        # Status filter
        st.markdown("** Filter by Status**")
        statuses = (
            sorted(raw_df["Status"].dropna().unique().tolist())
            if "Status" in raw_df.columns
            else []
        )
        selected_statuses = st.multiselect(
            "Select statuses",
            options=statuses,
            default=statuses,
            label_visibility="collapsed",
            key="status_filter",
        )

        st.markdown("---")
        st.success(f" {len(raw_df):,} work orders loaded")
        filename = st.session_state.get("wo_filename", "")
        if filename:
            st.caption(f"Source: `{filename}`")

    else:
        st.info(
            "No data loaded. Go to **Upload Work Orders** to import your CSV.",
            icon="ℹ️",
        )
        date_range = None
        selected_buildings = []
        selected_statuses = []

    st.markdown("---")
    st.caption("Riseboro Predictive Analytics v1.0")


# ─────────────────────────────────────────────────────────────────────────────
# HERO BANNER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="hero-banner">
        <h1> RB Prevent Dashboard</h1>
        <p>Maintenance analytics — spend, status, and building performance at a glance.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# EMPTY STATE GATE
# ─────────────────────────────────────────────────────────────────────────────
if not has_data:
    st.markdown(
        """
        <div class="empty-state">
            <div style="font-size:3rem;"></div>
            <h2>No work-order data loaded</h2>
            <p>Head to <strong>Upload Work Orders</strong> in the sidebar to import your CSV,<br>
            then return here to see your analytics.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()


# ─────────────────────────────────────────────────────────────────────────────
# APPLY FILTERS
# ─────────────────────────────────────────────────────────────────────────────
df = raw_df.copy()

# Date range
if date_range and isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_dt, end_dt = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
    if "Call Date" in df.columns:
        df = df[df["Call Date"].between(start_dt, end_dt, inclusive="both")]

# Building
if selected_buildings and "Building" in df.columns:
    df = df[df["Building"].isin(selected_buildings)]

# Status
if selected_statuses and "Status" in df.columns:
    df = df[df["Status"].isin(selected_statuses)]

# ── Critical Maintenance KPIs ────────────────────────────────────────────────
section_header(
    "️ Critical Maintenance KPIs",
    "Tracked categories: Leaks, Elevators, Heat, Hot Water, Roof",
)
divider()

target_categories = ["Leaks", "Elevators", "Heat", "Hot Water", "Roof"]

# Calculate 3-year threshold relative to max Call Date in raw_df
if "Call Date" in raw_df.columns and raw_df["Call Date"].notna().any():
    max_call_date = raw_df["Call Date"].max()
    three_years_ago = max_call_date - pd.DateOffset(years=3)
else:
    max_call_date = pd.Timestamp.now()
    three_years_ago = max_call_date - pd.DateOffset(years=3)

# Filter raw_df for target categories and last 3 years
recent_raw = raw_df[
    raw_df["issue_category"].isin(target_categories)
    & (raw_df["Call Date"] >= three_years_ago)
]

# Calculate high-volume counts for each category
category_high_vol_bldgs = {}
for cat in target_categories:
    cat_recent = recent_raw[recent_raw["issue_category"] == cat]
    cat_bldg_counts = cat_recent.groupby("Building").size()
    category_high_vol_bldgs[cat] = len(cat_bldg_counts[cat_bldg_counts > 3])

# Filtered counts
filtered_counts = {}
for cat in target_categories:
    filtered_counts[cat] = (df["issue_category"] == cat).sum()

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    h_bldgs = category_high_vol_bldgs["Leaks"]
    metric_card(
        "Leaks",
        f"{filtered_counts['Leaks']:,}",
        f"{h_bldgs} high-vol bldgs" if h_bldgs > 0 else "0 high-vol bldgs",
        h_bldgs == 0,
        "",
        show_arrow=False,
    )
with c2:
    h_bldgs = category_high_vol_bldgs["Elevators"]
    metric_card(
        "Elevators",
        f"{filtered_counts['Elevators']:,}",
        f"{h_bldgs} high-vol bldgs" if h_bldgs > 0 else "0 high-vol bldgs",
        h_bldgs == 0,
        "",
        show_arrow=False,
    )
with c3:
    h_bldgs = category_high_vol_bldgs["Heat"]
    metric_card(
        "Heat",
        f"{filtered_counts['Heat']:,}",
        f"{h_bldgs} high-vol bldgs" if h_bldgs > 0 else "0 high-vol bldgs",
        h_bldgs == 0,
        "",
        show_arrow=False,
    )
with c4:
    h_bldgs = category_high_vol_bldgs["Hot Water"]
    metric_card(
        "Hot Water",
        f"{filtered_counts['Hot Water']:,}",
        f"{h_bldgs} high-vol bldgs" if h_bldgs > 0 else "0 high-vol bldgs",
        h_bldgs == 0,
        "",
        show_arrow=False,
    )
with c5:
    h_bldgs = category_high_vol_bldgs["Roof"]
    metric_card(
        "Roof",
        f"{filtered_counts['Roof']:,}",
        f"{h_bldgs} high-vol bldgs" if h_bldgs > 0 else "0 high-vol bldgs",
        h_bldgs == 0,
        "",
        show_arrow=False,
    )
st.markdown("<br>", unsafe_allow_html=True)

_bc_path = os.path.join(os.path.dirname(__file__), "..", "data", "building_codes.csv")
_map_cols = [
    "YARDI Property Code_2", "PLACE_NAME", "ADDRESS", "Borough",
    "TOTALUNITS", "Status", "lat", "lon",
]
maps_df = pd.read_csv(_bc_path, usecols=_map_cols).dropna(subset=["lat", "lon"])
maps_df = maps_df.fillna({
    "PLACE_NAME": "—", "ADDRESS": "—", "Borough": "—",
    "TOTALUNITS": 0, "Status": "—", "YARDI Property Code_2": "",
})
maps_df["TOTALUNITS"] = maps_df["TOTALUNITS"].apply(
    lambda v: int(float(v)) if str(v).replace(".", "", 1).isdigit() else 0
)
maps_df["ADDRESS"] = maps_df["ADDRESS"].str.replace(r"\s+", " ", regex=True).str.strip()

# ── Join work-order counts (past 3 years) onto map data ──────────────────
maps_df["_yardi_key"] = (
    maps_df["YARDI Property Code_2"].astype(str).str.strip().str.lstrip(".").str.lower()
)
_three_years_ago = pd.Timestamp.now() - pd.DateOffset(years=3)
if "Call Date" in df.columns:
    _recent_wo = df[df["Call Date"] >= _three_years_ago]
else:
    _recent_wo = df
_wo_counts = (
    _recent_wo.groupby("Building")
    .size()
    .reset_index(name="wo_count")
)
_wo_counts["_yardi_key"] = _wo_counts["Building"].astype(str).str.strip().str.lower()
maps_df = maps_df.merge(
    _wo_counts[["_yardi_key", "wo_count"]], on="_yardi_key", how="left"
)
maps_df["wo_count"] = maps_df["wo_count"].fillna(0).astype(int)
maps_df = maps_df.drop(columns=["_yardi_key", "YARDI Property Code_2"], errors="ignore")

# ── Color: green (0 WOs) → yellow → red (max WOs) ───────────────────────
_max_wo = max(maps_df["wo_count"].max(), 1)

def _wo_color(count):
    t = min(count / _max_wo, 1.0)
    if t < 0.5:
        # green → yellow
        r = int(255 * (t * 2))
        g = 200
    else:
        # yellow → red
        r = 255
        g = int(200 * (1 - (t - 0.5) * 2))
    return [r, g, 30, 200]

maps_df["_color"] = maps_df["wo_count"].apply(_wo_color)

# ── Size: scale radius by total units ────────────────────────────────────
_max_units = max(maps_df["TOTALUNITS"].max(), 1)
maps_df["_radius"] = (
    50 + (maps_df["TOTALUNITS"] / _max_units) * 450
).astype(int)

st.pydeck_chart(
    pdk.Deck(
        map_style=None,
        initial_view_state=pdk.ViewState(
            latitude=40.69,
            longitude=-73.92,
            zoom=11,
        ),
        layers=[
            pdk.Layer(
                "ScatterplotLayer",
                data=maps_df,
                get_position="[lon, lat]",
                get_fill_color="_color",
                get_line_color=[255, 255, 255, 80],
                line_width_min_pixels=1,
                radius_min_pixels=4,
                radius_max_pixels=25,
                get_radius="_radius",
                radius_scale=1,
                pickable=True,
                auto_highlight=True,
                highlight_color=[30, 136, 229, 160],
            ),
        ],
        tooltip={
            "html": (
                "<div style='font-family: Inter, system-ui, sans-serif; padding: 6px 10px;'>"
                "<div style='font-weight:700; font-size:14px; margin-bottom:4px; color:#fff;'>"
                "{PLACE_NAME}</div>"
                "<div style='font-size:12px; color:#cfd8dc; margin-bottom:2px;'>"
                "📍 {ADDRESS}</div>"
                "<div style='font-size:12px; color:#cfd8dc; margin-bottom:2px;'>"
                "🏙️ {Borough}</div>"
                "<div style='font-size:12px; color:#cfd8dc; margin-bottom:2px;'>"
                "🏢 {TOTALUNITS} units</div>"
                "<div style='font-size:12px; color:#cfd8dc; margin-bottom:2px;'>"
                "📋 {Status}</div>"
                "<div style='font-size:13px; font-weight:600; color:#ffab40; margin-top:4px;'>"
                "🔧 {wo_count} work orders (3 yr)</div>"
                "</div>"
            ),
            "style": {
                "backgroundColor": "#1a2332",
                "color": "#ffffff",
                "borderRadius": "8px",
                "border": "1px solid #2a3f5f",
                "boxShadow": "0 4px 12px rgba(0,0,0,0.4)",
            },
        },
    )
)
st.markdown("<br>", unsafe_allow_html=True)

# ── High-Volume Tracking & Seasonal Trends ───────────────────────────────────
section_header(
    " High-Volume Tracking & Seasonal Trends",
    "Analysis of critical issues over time and across the portfolio",
)
divider()

col_l, col_r = st.columns([4, 5])

# Left column: Seasonal Breakdown
with col_l:
    st.markdown(
        '<div class="chart-card"><div class="chart-card-title">️ Seasonal Breakdown of Issues (Filtered Data)</div>',
        unsafe_allow_html=True,
    )
    seasonal_df = df[df["issue_category"].isin(target_categories)]
    if not seasonal_df.empty and "season" in seasonal_df.columns:
        seasonal_pivot = (
            seasonal_df.groupby(["season", "issue_category"])
            .size()
            .unstack(fill_value=0)
        )
        seasons_order = ["Winter", "Spring", "Summer", "Fall"]
        seasonal_pivot = seasonal_pivot.reindex(seasons_order, fill_value=0)
        for cat in target_categories:
            if cat not in seasonal_pivot.columns:
                seasonal_pivot[cat] = 0

        colors_mapping = {
            "Leaks": "#1e88e5",  # Light Blue
            "Elevators": "#8e24aa",  # Purple
            "Heat": "#e53935",  # Red
            "Hot Water": "#fb8c00",  # Orange
            "Roof": "#43a047",  # Green
        }

        seasonal_series = []
        for cat in target_categories:
            seasonal_series.append(
                {
                    "name": cat,
                    "type": "bar",
                    "stack": "total",
                    "data": seasonal_pivot[cat].tolist(),
                    "itemStyle": {"borderRadius": [4, 4, 0, 0]},
                }
            )

        seasonal_opts = {
            "color": [colors_mapping[cat] for cat in target_categories],
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "legend": {"data": target_categories, "bottom": 0},
            "grid": {
                "left": "3%",
                "right": "4%",
                "bottom": "12%",
                "containLabel": True,
            },
            "xAxis": {"type": "category", "data": seasons_order},
            "yAxis": {"type": "value", "name": "Reports"},
            "series": seasonal_series,
        }
        st_echarts(
            options=seasonal_opts, height="380px", key="seasonal_breakdown_chart"
        )
    else:
        st.info("No seasonal data available. Verify Call Date contains valid dates.")
    st.markdown("</div>", unsafe_allow_html=True)

# Right column: High-Volume Portfolio Tracking
with col_r:
    st.markdown(
        '<div class="chart-card"><div class="chart-card-title"> High-Volume Issue Tracking (Last 3 Years)</div>',
        unsafe_allow_html=True,
    )

    # High volume building tracking (>3 reports in last 3 years)
    bldg_piv = (
        recent_raw.groupby(["Building", "issue_category"]).size().unstack(fill_value=0)
    )
    for cat in target_categories:
        if cat not in bldg_piv.columns:
            bldg_piv[cat] = 0
    bldg_piv = bldg_piv[target_categories]
    bldg_piv["Total Target Reports"] = bldg_piv.sum(axis=1)
    high_vol_bldgs = (
        bldg_piv[bldg_piv["Total Target Reports"] > 3]
        .sort_values("Total Target Reports", ascending=False)
        .reset_index()
    )

    bldg_cols = ["Building", "bc_ADDRESS", "bc_Borough", "bc_PROJECT_NAME"]
    if "bc_Most recent rehab" in raw_df.columns:
        bldg_cols.append("bc_Most recent rehab")

    bldg_info = raw_df[bldg_cols].drop_duplicates(subset=["Building"])

    high_vol_bldgs = high_vol_bldgs.merge(bldg_info, on="Building", how="left")
    high_vol_bldgs["bc_ADDRESS"] = high_vol_bldgs["bc_ADDRESS"].fillna(
        "Unknown Address"
    )
    high_vol_bldgs["bc_Borough"] = high_vol_bldgs["bc_Borough"].fillna(
        "Unknown Borough"
    )
    high_vol_bldgs["bc_PROJECT_NAME"] = high_vol_bldgs["bc_PROJECT_NAME"].fillna(
        "Unknown Project"
    )

    def format_rehab(val):
        if pd.isna(val):
            return "N/A"
        s = str(val).strip()
        if not s or s.lower() in ("nan", "n/a", "none", "<na>"):
            return "N/A"
        if s.endswith(".0"):
            s = s[:-2]
        return s

    if "bc_Most recent rehab" in high_vol_bldgs.columns:
        high_vol_bldgs["bc_Most recent rehab"] = high_vol_bldgs[
            "bc_Most recent rehab"
        ].apply(format_rehab)
    else:
        high_vol_bldgs["bc_Most recent rehab"] = "N/A"

    # High volume unit tracking
    if "Prop-Unit" in raw_df.columns:
        unit_raw = recent_raw[recent_raw["Prop-Unit"] != "Building"]
        unit_piv = (
            unit_raw.groupby(["Building", "Prop-Unit", "issue_category"])
            .size()
            .unstack(fill_value=0)
        )
        for cat in target_categories:
            if cat not in unit_piv.columns:
                unit_piv[cat] = 0
        unit_piv = unit_piv[target_categories]
        unit_piv["Total Target Reports"] = unit_piv.sum(axis=1)
        high_vol_units = (
            unit_piv[unit_piv["Total Target Reports"] > 3]
            .sort_values("Total Target Reports", ascending=False)
            .reset_index()
        )
        high_vol_units = high_vol_units.merge(bldg_info, on="Building", how="left")
        high_vol_units["bc_ADDRESS"] = high_vol_units["bc_ADDRESS"].fillna(
            "Unknown Address"
        )
        high_vol_units["bc_Borough"] = high_vol_units["bc_Borough"].fillna(
            "Unknown Borough"
        )
        high_vol_units["bc_PROJECT_NAME"] = high_vol_units["bc_PROJECT_NAME"].fillna(
            "Unknown Project"
        )
    else:
        high_vol_units = pd.DataFrame()

    tab_bldg, tab_unit = st.tabs([" High-Vol Buildings", " High-Vol Units"])

    with tab_bldg:
        st.caption(
            "Buildings with >3 target reports (Leaks, Elevators, Heat, Hot Water, Roof) in the last 3 years."
        )
        if not high_vol_bldgs.empty:
            bldgs_display = high_vol_bldgs[
                [
                    "Building",
                    "bc_PROJECT_NAME",
                    "bc_ADDRESS",
                    "bc_Most recent rehab",
                    "Leaks",
                    "Elevators",
                    "Heat",
                    "Hot Water",
                    "Roof",
                    "Total Target Reports",
                ]
            ].copy()
            bldgs_display.columns = [
                "Building Code",
                "Project Name",
                "Address",
                "Most Recent Rehab",
                "Leaks",
                "Elevators",
                "Heat",
                "Hot Water",
                "Roof",
                "Total",
            ]
            st.dataframe(
                bldgs_display,
                column_config={
                    "Building Code": st.column_config.TextColumn("Entity", pinned=True),
                    "Project Name": st.column_config.TextColumn("Project"),
                    "Address": st.column_config.TextColumn("Address"),
                    "Most Recent Rehab": st.column_config.TextColumn(
                        "Most Recent Rehab"
                    ),
                    "Leaks": st.column_config.NumberColumn("Leaks", format="%d"),
                    "Elevators": st.column_config.NumberColumn(
                        "Elevators", format="%d"
                    ),
                    "Heat": st.column_config.NumberColumn("Heat", format="%d"),
                    "Hot Water": st.column_config.NumberColumn(
                        "Hot Water", format="%d"
                    ),
                    "Roof": st.column_config.NumberColumn("Roof", format="%d"),
                    "Total": st.column_config.NumberColumn("Total", format="%d"),
                },
                hide_index=True,
                height=300,
            )
        else:
            st.success(
                "No buildings identified with more than 3 target reports in the last 3 years."
            )

    with tab_unit:
        st.caption("Individual units with >3 target reports in the last 3 years.")
        if not high_vol_units.empty:
            units_display = high_vol_units[
                [
                    "Building",
                    "Prop-Unit",
                    "bc_PROJECT_NAME",
                    "Leaks",
                    "Elevators",
                    "Heat",
                    "Hot Water",
                    "Roof",
                    "Total Target Reports",
                ]
            ].copy()
            units_display.columns = [
                "Building Code",
                "Unit",
                "Project Name",
                "Leaks",
                "Elevators",
                "Heat",
                "Hot Water",
                "Roof",
                "Total",
            ]
            st.dataframe(
                units_display,
                column_config={
                    "Building Code": st.column_config.TextColumn(
                        "Building", pinned=True
                    ),
                    "Unit": st.column_config.TextColumn("Unit", pinned=True),
                    "Project Name": st.column_config.TextColumn("Project"),
                    "Leaks": st.column_config.NumberColumn("Leaks", format="%d"),
                    "Elevators": st.column_config.NumberColumn(
                        "Elevators", format="%d"
                    ),
                    "Heat": st.column_config.NumberColumn("Heat", format="%d"),
                    "Hot Water": st.column_config.NumberColumn(
                        "Hot Water", format="%d"
                    ),
                    "Roof": st.column_config.NumberColumn("Roof", format="%d"),
                    "Total": st.column_config.NumberColumn("Total", format="%d"),
                },
                hide_index=True,
                height=300,
            )
        else:
            st.success(
                "No individual units identified with more than 3 target reports in the last 3 years."
            )

    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# UNIT-LEVEL ANALYTICS & STATISTICAL TRENDS
# ─────────────────────────────────────────────────────────────────────────────
section_header(
    "Unit-Level Hotspots & Trend Analysis",
    "Deep-dive into individual apartment work-order volume, issue profiles, and statistical significance",
)
divider()

# Filter raw dataset for the past 3 years for unit-level analysis
if "Call Date" in raw_df.columns and raw_df["Call Date"].notna().any():
    raw_recent_all = raw_df[raw_df["Call Date"] >= three_years_ago]
else:
    raw_recent_all = raw_df

unit_adapted = adapt_for_analysis(raw_recent_all)
apts_df = exclude_non_apartments(unit_adapted) if not unit_adapted.empty else pd.DataFrame()

if not apts_df.empty and "prop_unit" in apts_df.columns and apts_df["prop_unit"].nunique() > 0:
    total_apts = apts_df["prop_unit"].nunique()
    total_apt_wos = len(apts_df)
    avg_wo_per_unit = total_apt_wos / total_apts if total_apts > 0 else 0
    top_10_pct_count = max(1, int(total_apts * 0.10))
    top_10_pct_units = apts_df["prop_unit"].value_counts().head(top_10_pct_count).index
    top_10_pct_wos = apts_df[apts_df["prop_unit"].isin(top_10_pct_units)]
    top_10_pct_avg = len(top_10_pct_wos) / top_10_pct_count if top_10_pct_count > 0 else 0

    # Top issue category across all apartments
    top_cat_counts = apts_df["final_category"].value_counts()
    dominant_cat = top_cat_counts.index[0] if not top_cat_counts.empty else "N/A"
    dominant_cat_share = (
        (top_cat_counts.iloc[0] / total_apt_wos * 100) if total_apt_wos > 0 else 0
    )

    # 4 Unit KPI Summary Cards
    u_c1, u_c2, u_c3, u_c4 = st.columns(4)
    with u_c1:
        metric_card(
            "Apartments Analyzed",
            f"{total_apts:,}",
            "3-Year Window",
            True,
            show_arrow=False,
        )
    with u_c2:
        metric_card(
            "Portfolio Avg WOs/Unit",
            f"{avg_wo_per_unit:.1f}",
            f"{total_apt_wos:,} total WOs",
            True,
            show_arrow=False,
        )
    with u_c3:
        metric_card(
            "Top 10% Units Avg WOs",
            f"{top_10_pct_avg:.1f}",
            f"{top_10_pct_avg / max(avg_wo_per_unit, 0.01):.1f}x portfolio avg",
            False,
            show_arrow=True,
        )
    with u_c4:
        metric_card(
            "Dominant Apartment Issue",
            f"{dominant_cat}",
            f"{dominant_cat_share:.1f}% of apartment WOs",
            True,
            show_arrow=False,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Hotspot Tables (Top Units & Group Comparison) ────────────────────────
    col_u_left, col_u_right = st.columns([5, 4])

    with col_u_left:
        st.markdown(
            '<div class="chart-card"><div class="chart-card-title">Top Work-Order Hotspot Units (Top 15)</div>',
            unsafe_allow_html=True,
        )
        top_units_count = min(15, total_apts)
        top_detail_df = top_units_detail(apts_df, n=top_units_count).reset_index()

        def _fmt_res_table(v):
            if pd.isna(v) or v is None:
                return "N/A"
            if v == 0:
                return "Same day (<1d)"
            elif v < 1:
                return f"{v*24:.0f} hrs"
            else:
                return f"{v:.1f} days"

        top_detail_df["Avg Resolution (Days)"] = top_detail_df[
            "Avg Resolution (Days)"
        ].apply(_fmt_res_table)

        st.dataframe(
            top_detail_df,
            column_config={
                "Unit": st.column_config.TextColumn("Unit", pinned=True),
                "Property": st.column_config.TextColumn("Property / Project"),
                "Total WOs": st.column_config.NumberColumn(
                    "Total WOs", format="%d"
                ),
                "Avg Resolution (Days)": st.column_config.TextColumn(
                    "Avg Resolution"
                ),
                "Primary Issue (Share %)": st.column_config.TextColumn(
                    "Dominant Issue"
                ),
            },
            hide_index=True,
            height=320,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_u_right:
        st.markdown(
            '<div class="chart-card"><div class="chart-card-title">Portfolio vs. Hotspot Comparison</div>',
            unsafe_allow_html=True,
        )
        # Select categories for comparison
        active_cats = [
            c for c in target_categories if c in apts_df["final_category"].unique()
        ]
        if not active_cats:
            active_cats = apts_df["final_category"].value_counts().head(5).index.tolist()

        comp_table = compare_groups(apts_df, categories=active_cats).reset_index()
        comp_table = comp_table.rename(columns={"index": "Cohort"})

        # Format column values
        if "Units" in comp_table.columns:
            comp_table["Units"] = comp_table["Units"].astype(int)
        if "Avg WOs/Unit" in comp_table.columns:
            comp_table["Avg WOs/Unit"] = comp_table["Avg WOs/Unit"].round(1)
        if "Avg Resolution (Days)" in comp_table.columns:
            comp_table["Avg Resolution (Days)"] = comp_table[
                "Avg Resolution (Days)"
            ].apply(lambda v: f"{v:.1f} d" if pd.notna(v) and v > 0 else ("<1 d" if pd.notna(v) and v == 0 else "N/A"))

        for cat in active_cats:
            col_name = f"{cat} %"
            if col_name in comp_table.columns:
                comp_table[col_name] = comp_table[col_name].apply(
                    lambda v: f"{v:.1f}%" if pd.notna(v) else "0.0%"
                )

        st.dataframe(
            comp_table,
            column_config={
                "Cohort": st.column_config.TextColumn("Cohort", pinned=True),
                "Units": st.column_config.NumberColumn("Units", format="%d"),
                "Avg WOs/Unit": st.column_config.NumberColumn(
                    "Avg WOs", format="%.1f"
                ),
                "Avg Resolution (Days)": st.column_config.TextColumn("Resolution"),
            },
            hide_index=True,
            height=320,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Per-Unit Interactive Deep Dive & Statistical Significance ────────────
    st.markdown(
        '<div class="chart-card"><div class="chart-card-title">Individual Unit Deep Dive & Statistical Trends</div>',
        unsafe_allow_html=True,
    )

    all_unit_options = apts_df["prop_unit"].value_counts().index.tolist()
    unit_labels = {
        u: f"Code {u} ({apts_df[apts_df['prop_unit'] == u]['property_name'].iloc[0]} - {len(apts_df[apts_df['prop_unit'] == u])} WOs)"
        for u in all_unit_options
    }

    selected_unit = st.selectbox(
        "Select apartment unit to profile:",
        options=all_unit_options,
        format_func=lambda x: unit_labels.get(x, str(x)),
        key="unit_drilldown_selector",
    )

    if selected_unit:
        u_df = apts_df[apts_df["prop_unit"] == selected_unit]
        u_prop = u_df["property_name"].iloc[0] if not u_df.empty else "Unknown"
        u_total = len(u_df)
        u_top_cat_counts = u_df["final_category"].value_counts()
        u_top_cat = (
            u_top_cat_counts.index[0] if not u_top_cat_counts.empty else "N/A"
        )
        u_top_cat_pct = (
            (u_top_cat_counts.iloc[0] / u_total * 100) if u_total > 0 else 0
        )
        u_res = u_df["ttl_days"].mean()
        if pd.isna(u_res):
            u_res_str = "N/A"
        elif u_res == 0:
            u_res_str = "Same day (<1 day)"
        elif u_res < 1:
            u_res_str = f"{u_res*24:.0f} hours"
        else:
            u_res_str = f"{u_res:.1f} days"

        st.markdown(
            f"""
            <div style="background:#f8fafc; border-radius:12px; padding:12px 18px; margin-bottom:1.2rem; border:1px solid #e2e8f0; display:flex; flex-wrap:wrap; gap:20px; align-items:center;">
                <div><strong style="color:#013494;">Code:</strong> <span style="font-size:1.05rem; font-weight:700;">{selected_unit}</span></div>
                <div><strong style="color:#013494;">Property:</strong> {u_prop}</div>
                <div><strong style="color:#013494;">Total 3-Yr WOs:</strong> <span style="font-weight:700; color:#e53935;">{u_total}</span></div>
                <div><strong style="color:#013494;">Dominant Category:</strong> {u_top_cat} ({u_top_cat_pct:.1f}%)</div>
                <div><strong style="color:#013494;">Avg Resolution Time:</strong> {u_res_str}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_trend_l, col_trend_r = st.columns([1, 1])

        with col_trend_l:
            u_yearly = yearly_counts(u_df)
            years_list = [str(y) for y in u_yearly.index.tolist()]
            counts_list = u_yearly.values.tolist()

            yearly_chart_opts = {
                "color": [PRIMARY],
                "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                "grid": {
                    "left": "3%",
                    "right": "4%",
                    "bottom": "10%",
                    "containLabel": True,
                },
                "xAxis": {
                    "type": "category",
                    "data": years_list,
                    "name": "Year",
                },
                "yAxis": {"type": "value", "name": "Work Orders"},
                "series": [
                    {
                        "name": "Work Orders",
                        "type": "bar",
                        "data": counts_list,
                        "itemStyle": {
                            "borderRadius": [4, 4, 0, 0],
                            "color": PRIMARY,
                        },
                        "emphasis": {"itemStyle": {"color": PRIMARY_L}},
                    }
                ],
            }
            st.markdown(
                f"<div style='font-weight:600; color:#013494; margin-bottom:6px;'>Yearly Volume Trend (Unit {selected_unit})</div>",
                unsafe_allow_html=True,
            )
            st_echarts(
                options=yearly_chart_opts,
                height="280px",
                key=f"unit_yearly_chart_{selected_unit}",
            )

        with col_trend_r:
            # ── Breakdown Monthly Seasonality by Category ────────────────────────
            cat_palette = {
                "Leaks": "#1e88e5",
                "Elevators": "#8e24aa",
                "Heat": "#e53935",
                "Hot Water": "#fb8c00",
                "Roof": "#43a047",
                "Plumbing": "#0288d1",
                "Extermination": "#689f38",
                "Appliances": "#0097a7",
                "Doors and Locks": "#5c6bc0",
                "Electrical": "#fbc02d",
                "Painting and Plastering": "#795548",
            }
            
            unit_cats = [c for c in u_df["final_category"].value_counts().index.tolist() if pd.notna(c)]
            if not unit_cats:
                unit_cats = ["Other"]
            
            # Pivot by Month_Num (1..12) and final_category
            u_month_cat = (
                u_df.groupby(["Month_Num", "final_category"])
                .size()
                .unstack(fill_value=0)
            )
            u_month_cat = u_month_cat.reindex(range(1, 13), fill_value=0)
            months_labels = [MONTH_MAP.get(m, str(m))[:3] for m in range(1, 13)]
            
            # Build stacked series per category
            monthly_series = []
            chart_colors = []
            for i, cat in enumerate(unit_cats):
                cat_color = cat_palette.get(cat, COLORS[i % len(COLORS)])
                chart_colors.append(cat_color)
                cat_data = u_month_cat[cat].tolist() if cat in u_month_cat.columns else [0] * 12
                monthly_series.append(
                    {
                        "name": cat,
                        "type": "bar",
                        "stack": "total",
                        "data": cat_data,
                        "itemStyle": {"borderRadius": [2, 2, 0, 0], "color": cat_color},
                        "emphasis": {"focus": "series"},
                    }
                )

            monthly_chart_opts = {
                "color": chart_colors,
                "tooltip": {
                    "trigger": "axis",
                    "axisPointer": {"type": "shadow"},
                },
                "legend": {
                    "data": unit_cats,
                    "bottom": 0,
                    "type": "scroll",
                    "textStyle": {"fontSize": 11},
                },
                "grid": {
                    "left": "3%",
                    "right": "4%",
                    "bottom": "18%",
                    "containLabel": True,
                },
                "xAxis": {
                    "type": "category",
                    "data": months_labels,
                    "name": "Month",
                },
                "yAxis": {"type": "value", "name": "Work Orders"},
                "series": monthly_series,
            }
            st.markdown(
                f"<div style='font-weight:600; color:#013494; margin-bottom:6px;'>Monthly Seasonality by Category (Unit {selected_unit})</div>",
                unsafe_allow_html=True,
            )
            st_echarts(
                options=monthly_chart_opts,
                height="280px",
                key=f"unit_monthly_chart_{selected_unit}",
            )

        # ── Statistical Tests & Significance ─────────────────────────────────
        st.markdown("<hr style='margin:1rem 0; border-color:#e2e8f0;'>", unsafe_allow_html=True)
        st.markdown("<div style='font-weight:700; color:#013494; margin-bottom:8px;'>Statistical Significance Analysis</div>", unsafe_allow_html=True)

        col_sig1, col_sig2 = st.columns([1, 1])

        # Test 1: Linear yearly trend
        with col_sig1:
            trend_res = yearly_trend(u_df, exclude_year=None)
            if trend_res is not None:
                is_sig = trend_res.significant
                slope_dir = "Increasing" if trend_res.slope > 0 else "Decreasing"
                sig_badge = (
                    f"<span style='background:#fee2e2; color:#991b1b; padding:3px 8px; border-radius:6px; font-weight:600; font-size:0.85rem;'>Statistically Significant (p = {trend_res.p_value:.4f})</span>"
                    if is_sig
                    else f"<span style='background:#f1f5f9; color:#475569; padding:3px 8px; border-radius:6px; font-weight:500; font-size:0.85rem;'>No Significant Direction (p = {trend_res.p_value:.3f})</span>"
                )
                st.markdown(
                    f"""
                    <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:12px 16px;">
                        <div style="font-weight:600; font-size:0.95rem; margin-bottom:4px;">Long-Term Trajectory: {slope_dir}</div>
                        <div style="margin-bottom:6px;">{sig_badge}</div>
                        <div style="font-size:0.85rem; color:#64748b;">
                            Slope: <strong>{trend_res.slope:+.2f} WOs/yr</strong> &nbsp;·&nbsp; R² = {trend_res.r_squared:.2f} &nbsp;·&nbsp; {trend_res.n_years} years observed
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    """
                    <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:12px 16px;">
                        <div style="font-weight:600; font-size:0.95rem; margin-bottom:4px;">Long-Term Trajectory</div>
                        <div style="font-size:0.85rem; color:#64748b;">Requires ≥3 distinct calendar years with records to compute linear trend regression.</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # Test 2: Seasonality Chi-Square test & Category Breakdown
        with col_sig2:
            season_res = seasonality(u_df)
            if season_res is not None and u_total >= 10:
                is_seasonal = season_res.significant
                season_badge = (
                    f"<span style='background:#fef3c7; color:#92400e; padding:3px 8px; border-radius:6px; font-weight:600; font-size:0.85rem;'>Seasonal Variation Detected (p = {season_res.p_value:.4f})</span>"
                    if is_seasonal
                    else f"<span style='background:#f1f5f9; color:#475569; padding:3px 8px; border-radius:6px; font-weight:500; font-size:0.85rem;'>Uniform Throughout Year (p = {season_res.p_value:.3f})</span>"
                )
                
                # Compute category-specific peak months
                cat_peaks = []
                for cat in unit_cats:
                    cat_wos = u_df[u_df["final_category"] == cat]
                    if len(cat_wos) >= 2 and "Month_Num" in cat_wos.columns:
                        top_m = cat_wos["Month_Num"].value_counts().index[0]
                        m_cnt = cat_wos["Month_Num"].value_counts().iloc[0]
                        m_pct = (m_cnt / len(cat_wos)) * 100
                        cat_peaks.append(f"<strong>{cat}</strong>: peak in {MONTH_MAP.get(top_m, str(top_m))} ({m_cnt}/{len(cat_wos)} WOs, {m_pct:.0f}%)")
                
                cat_peaks_html = ""
                if cat_peaks:
                    cat_peaks_html = (
                        "<div style='font-size:0.82rem; color:#334155; margin-top:6px; background:#f8fafc; padding:6px 10px; border-radius:6px;'>"
                        "<div style='font-weight:600; color:#013494; margin-bottom:2px;'>Category Seasonal Peaks:</div>"
                        + "<br>".join(cat_peaks[:3])
                        + "</div>"
                    )

                # Check for specific outlier months overall
                outliers = month_outliers(season_res.monthly_counts)
                outlier_text = ""
                if outliers:
                    month_strs = [f"{MONTH_MAP.get(o.month, str(o.month))} ({o.direction.lower()}, {o.proportion*100:.0f}%)" for o in outliers]
                    outlier_text = f"<div style='font-size:0.85rem; color:#013494; margin-top:4px;'>Portfolio Outlier Months: {', '.join(month_strs)}</div>"

                st.markdown(
                    f"""
                    <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:12px 16px;">
                        <div style="font-weight:600; font-size:0.95rem; margin-bottom:4px;">Monthly Seasonality by Category (Chi-Square)</div>
                        <div style="margin-bottom:6px;">{season_badge}</div>
                        <div style="font-size:0.85rem; color:#64748b;">
                            Overall Chi² = {season_res.chi2:.2f} (df=11)
                        </div>
                        {outlier_text}
                        {cat_peaks_html}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    """
                    <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:12px 16px;">
                        <div style="font-weight:600; font-size:0.95rem; margin-bottom:4px;">Monthly Seasonality by Category</div>
                        <div style="font-size:0.85rem; color:#64748b;">Unit volume (&lt;10 WOs) too low for reliable chi-square goodness-of-fit testing.</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.markdown("</div>", unsafe_allow_html=True)
else:
    st.info("No individual apartment unit data found in the uploaded work orders.")

st.markdown("<br>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# ROW 1 — WO Volume over Time + Status Distribution
# ─────────────────────────────────────────────────────────────────────────────
section_header("Volume & Status")
divider()

col_l, col_r = st.columns([3, 2])

# ── Work Orders by Month ──────────────────────────────────────────────────────
with col_l:
    st.markdown(
        '<div class="chart-card"><div class="chart-card-title"> Work Orders by Month (Call Date)</div>',
        unsafe_allow_html=True,
    )

    if "Call Date" in df.columns and df["Call Date"].notna().any():
        monthly = (
            df.assign(month=df["Call Date"].dt.to_period("M"))
            .groupby("month")
            .size()
            .reset_index(name="count")
            .sort_values("month")
        )
        monthly["month"] = monthly["month"].astype(str)

        vol_opts = {
            "color": [PRIMARY],
            "tooltip": {"trigger": "axis"},
            "grid": {
                "left": "3%",
                "right": "4%",
                "bottom": "10%",
                "containLabel": True,
            },
            "xAxis": {
                "type": "category",
                "data": monthly["month"].tolist(),
                "axisLabel": {"rotate": 30},
            },
            "yAxis": {"type": "value", "name": "Work Orders"},
            "series": [
                {
                    "name": "WOs",
                    "type": "bar",
                    "data": monthly["count"].tolist(),
                    "itemStyle": {"borderRadius": [4, 4, 0, 0], "color": PRIMARY},
                    "emphasis": {"itemStyle": {"color": PRIMARY_L}},
                }
            ],
        }
        st_echarts(options=vol_opts, height="350px", key="monthly_vol")
    else:
        st.info("No Call Date data available for timeline chart.")

    st.markdown("</div>", unsafe_allow_html=True)

# ── Status Donut ──────────────────────────────────────────────────────────────
with col_r:
    st.markdown(
        '<div class="chart-card"><div class="chart-card-title"> Status Distribution</div>',
        unsafe_allow_html=True,
    )

    if "Status" in df.columns:
        status_counts = df["Status"].value_counts().reset_index()
        status_counts.columns = ["name", "value"]
        pie_data = status_counts.to_dict("records")

        status_opts = {
            "color": COLORS,
            "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
            "legend": {"orient": "vertical", "left": "left", "top": "middle"},
            "series": [
                {
                    "name": "Status",
                    "type": "pie",
                    "radius": ["42%", "70%"],
                    "avoidLabelOverlap": False,
                    "itemStyle": {
                        "borderRadius": 8,
                        "borderColor": "#fff",
                        "borderWidth": 2,
                    },
                    "label": {"show": False, "position": "center"},
                    "emphasis": {
                        "label": {"show": True, "fontSize": 18, "fontWeight": "bold"}
                    },
                    "labelLine": {"show": False},
                    "data": pie_data,
                }
            ],
        }
        st_echarts(options=status_opts, height="350px", key="status_donut")
    else:
        st.info("No Status column available.")

    st.markdown("</div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown(
    """
    <div style="text-align:center; color:#94a3b8; font-size:0.8rem; padding:1rem 0;">
        Riseboro Predictive Analytics Dashboard &nbsp;·&nbsp; Built with Streamlit &amp; Apache ECharts
        &nbsp;·&nbsp; <a href="https://hoyalytics.org" style="color:#013494;">Hoyalytics</a>
    </div>
    """,
    unsafe_allow_html=True,
)
