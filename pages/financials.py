"""
pages/financials.py
-------------------
Riseboro Portfolio Financials & Economics Dashboard
Provides in-depth analytics on:
  1. Gross Potential Rent & Rent Roll Economics (data/units_rents.csv)
  2. Capital Development, LIHTC & Subsidy Stacks (data/building_codes.csv)
  3. Maintenance OpEx & Revenue Drag (Work Orders integration)
  4. Commercial Spaces & Asset Vintage (data/renovations.csv)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd
import streamlit as st
from streamlit_echarts import st_echarts

from src.components import divider, metric_card, section_header
from src.financials import (
    calculate_hpd_fee_kpis,
    calculate_maintenance_drag,
    calculate_portfolio_kpis,
    clean_currency,
    get_annual_fee_trend,
    get_bedroom_rent_summary,
    get_building_fee_summary,
    get_fee_source_distribution,
    get_fee_type_distribution,
    get_property_revenue_summary,
    get_rent_tier_distribution,
    load_building_financials,
    load_portfolio_hpd_charges,
    load_renovations,
    load_units_rents,
)

# ── Theme Palette ────────────────────────────────────────────────────────────
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

# ── Custom Page Styling ──────────────────────────────────────────────────────
st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

        .hero-banner {
            background: linear-gradient(120deg, #013494 0%, #0252cc 60%, #1565c0 100%);
            border-radius: 20px;
            padding: 2rem 2.5rem;
            color: white;
            margin-bottom: 1.5rem;
            box-shadow: 0 8px 32px rgba(1,52,148,0.3);
        }
        .hero-banner h1 { margin:0; font-size:1.85rem; font-weight:800; }
        .hero-banner p  { margin:0.4rem 0 0; opacity:.8; font-size:0.95rem; }

        .chart-card {
            background: white;
            border-radius: 16px;
            padding: 1.4rem;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06);
            margin-bottom: 1rem;
            border: 1px solid #e2e8f0;
        }
        .chart-card-title {
            color: #013494;
            font-weight: 700;
            font-size: 1.05rem;
            margin-bottom: 0.75rem;
        }

        .highlight-box {
            background: #f8fafc;
            border-left: 4px solid #013494;
            border-radius: 8px;
            padding: 1rem 1.25rem;
            margin: 0.75rem 0;
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #013494 0%, #0a2d6e 100%);
            color: white;
        }
        section[data-testid="stSidebar"] * { color: white; }
        section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.2); }
        section[data-testid="stSidebar"] input { color: #013494; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Load Core Financial Datasets ─────────────────────────────────────────────
units_df = load_units_rents()
building_df = load_building_financials()
renovations_df = load_renovations()
hpd_charges_df = load_portfolio_hpd_charges(renovations_df)
wo_df = st.session_state.get("wo_df", None)

if units_df.empty:
    st.error("Units & Rents dataset (`data/units_rents.csv`) could not be loaded.")
    st.stop()

# ── Sidebar Global Filters ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("##  Financial Filters")
    st.caption("Refine portfolio economics and unit distributions.")

    # Borough Filter
    available_boroughs = sorted([b for b in units_df["Display_Borough"].dropna().unique() if str(b).strip()])
    selected_boroughs = st.multiselect(
        "Borough",
        options=available_boroughs,
        default=[],
        placeholder="All Boroughs",
    )

    # Housing Type Filter
    available_housing = sorted([h for h in units_df["Display_Housing_Type"].dropna().unique() if str(h).strip()])
    selected_housing = st.multiselect(
        "Housing Type",
        options=available_housing,
        default=[],
        placeholder="All Housing Types",
    )

    # Property / Project Filter
    prop_options = sorted(units_df["Display_Property"].dropna().unique().tolist())
    selected_props = st.multiselect(
        "Property / Project",
        options=prop_options,
        default=[],
        placeholder="All Properties",
    )

    # Bedroom Filter
    bedroom_options = ["Studio (0BR)", "1 Bedroom", "2 Bedroom", "3 Bedroom", "4+ Bedroom"]
    selected_bedrooms = st.multiselect(
        "Bedrooms",
        options=bedroom_options,
        default=[],
        placeholder="All Bedroom Counts",
    )

    # Subsidized / Zero-rent Toggle
    exclude_zero_rent = st.toggle("Exclude Subsidized / $0 Units", value=False, help="Filter out non-revenue or fully subsidized units from rent averages.")

    st.markdown("---")
    st.markdown("###  Dataset Status")
    st.caption(f"• **Units in Rent Roll:** {len(units_df):,}")
    st.caption(f"• **Development Projects:** {building_df['PROJECT_NAME'].nunique():,}")
    st.caption(f"• **HPD Municipal Charges:** {len(hpd_charges_df):,} records")
    if wo_df is not None and not wo_df.empty:
        st.caption(f"• **Uploaded Work Orders:** {len(wo_df):,} rows")
    else:
        st.caption("• **Work Orders:** Not uploaded (Maintenance Drag disabled)")

# ── Apply Filters to Units DF ────────────────────────────────────────────────
filtered_units = units_df.copy()
if selected_boroughs:
    filtered_units = filtered_units[filtered_units["Display_Borough"].isin(selected_boroughs)]
if selected_housing:
    filtered_units = filtered_units[filtered_units["Display_Housing_Type"].isin(selected_housing)]
if selected_props:
    filtered_units = filtered_units[filtered_units["Display_Property"].isin(selected_props)]
if selected_bedrooms:
    filtered_units = filtered_units[filtered_units["Bedroom_Label"].isin(selected_bedrooms)]
if exclude_zero_rent:
    filtered_units = filtered_units[filtered_units["Rent_num"] > 0]

# Filter Building DF accordingly if project filtered
filtered_building = building_df.copy()
if selected_boroughs:
    filtered_building = filtered_building[filtered_building["Borough"].isin(selected_boroughs)]
if selected_housing:
    filtered_building = filtered_building[filtered_building["Housing_Type"].isin(selected_housing)]
if selected_props:
    filtered_building = filtered_building[
        filtered_building["PROJECT_NAME"].isin(selected_props) |
        filtered_building["PLACE_NAME"].isin(selected_props)
    ]

# Filter HPD Charges DF accordingly
filtered_charges = hpd_charges_df.copy()
if not filtered_charges.empty:
    if selected_boroughs:
        filtered_charges = filtered_charges[filtered_charges["Display_Borough"].isin(selected_boroughs)]
    if selected_props:
        filtered_charges = filtered_charges[
            filtered_charges["Display_Property"].isin(selected_props)
            | filtered_charges["PROJECT_NAME"].isin(selected_props)
            | filtered_charges["Matched_Address"].isin(selected_props)
        ]

# ── Hero Banner ──────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="hero-banner">
        <h1>Portfolio Financials & Economics</h1>
        <p>Comprehensive analysis of revenue economics, capital development stacks, LIHTC subsidies, and maintenance OpEx drag.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Portfolio Top-Level KPI Summary ──────────────────────────────────────────
kpis = calculate_portfolio_kpis(filtered_units, filtered_building)

col1, col2, col3, col4 = st.columns(4)
with col1:
    metric_card(
        label="Annual Gross Rent Roll",
        value=f"${kpis['annual_gpr']:,.0f}" if kpis["annual_gpr"] < 1e6 else f"${kpis['annual_gpr'] / 1e6:.2f}M",
        delta=f"${kpis['monthly_gpr']:,.0f}/mo",
        delta_positive=True,
        
        show_arrow=False,
    )
with col2:
    metric_card(
        label="Average Monthly Rent",
        value=f"${kpis['avg_rent_paying']:,.0f}",
        delta=f"Median: ${kpis['median_rent']:,.0f}",
        delta_positive=True,
        
        show_arrow=False,
    )
with col3:
    metric_card(
        label="Residential Units",
        value=f"{kpis['total_units']:,}",
        delta=f"{kpis['active_paying_units']:,} paying | {kpis['subsidized_zero_units']:,} sub",
        delta_positive=True,
        
        show_arrow=False,
    )
with col4:
    tdc_val = kpis["total_tdc"]
    tdc_str = f"${tdc_val / 1e9:.2f}B" if tdc_val >= 1e9 else (f"${tdc_val / 1e6:.1f}M" if tdc_val >= 1e6 else f"${tdc_val:,.0f}")
    metric_card(
        label="Total Capital Investment (TDC)",
        value=tdc_str,
        delta=f"{filtered_building['PROJECT_NAME'].nunique()} projects",
        delta_positive=True,
        
        show_arrow=False,
    )

st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)

# ── Main Tabs Navigation ─────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    " Rent Roll & Revenue",
    " Capital & Development",
    " Maintenance OpEx & Drag",
    " Commercial & Vintage",
    "🏛️ HPD Charges & Municipal Fees",
])

# ═════════════════════════════════════════════════════════════════════════════
# TAB 1: RENT ROLL & REVENUE ECONOMICS
# ═════════════════════════════════════════════════════════════════════════════
with tab1:
    section_header(
        "Rent Roll & Revenue Economics",
        "Analyze gross potential revenue, rent distribution tiers, and unit-level bedroom economics.",
    )

    prop_revenue = get_property_revenue_summary(filtered_units)
    tier_dist = get_rent_tier_distribution(filtered_units)
    bed_summary = get_bedroom_rent_summary(filtered_units)

    # 1. Top Properties by Rent Roll & Rent Tier Breakdown
    c_left, c_right = st.columns([1.4, 1])

    with c_left:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown('<div class="chart-card-title"> Top Properties by Monthly Rent Roll</div>', unsafe_allow_html=True)

        top_10_props = prop_revenue.head(10).iloc[::-1]  # Reverse for bottom-up horizontal chart
        if not top_10_props.empty:
            chart_options = {
                "tooltip": {
                    "trigger": "axis",
                    "axisPointer": {"type": "shadow"},
                    "formatter": "{b}: <b>${c:,.0f} / mo</b>",
                },
                "grid": {"left": "3%", "right": "6%", "bottom": "3%", "top": "3%", "containLabel": True},
                "xAxis": {
                    "type": "value",
                    "axisLabel": {
                        "formatter": "${value}",
                        "color": "#64748b",
                    },
                    "splitLine": {"lineStyle": {"color": "#f1f5f9"}},
                },
                "yAxis": {
                    "type": "category",
                    "data": top_10_props["Display_Property"].tolist(),
                    "axisLabel": {"color": "#334155", "fontSize": 11},
                },
                "series": [
                    {
                        "name": "Monthly Rent Roll",
                        "type": "bar",
                        "data": top_10_props["monthly_rent_roll"].round(2).tolist(),
                        "itemStyle": {
                            "color": {
                                "type": "linear",
                                "x": 0, "y": 0, "x2": 1, "y2": 0,
                                "colorStops": [
                                    {"offset": 0, "color": PRIMARY},
                                    {"offset": 1, "color": "#1e88e5"},
                                ],
                            },
                            "borderRadius": [0, 6, 6, 0],
                        },
                    }
                ],
            }
            st_echarts(chart_options, height="380px")
        else:
            st.info("No property revenue data available for current filter selection.")
        st.markdown("</div>", unsafe_allow_html=True)

    with c_right:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown('<div class="chart-card-title"> Unit Distribution by Rent Tier</div>', unsafe_allow_html=True)

        if not tier_dist.empty:
            pie_data = [
                {"name": row["Rent_Tier"], "value": int(row["unit_count"])}
                for _, row in tier_dist.iterrows()
                if row["unit_count"] > 0
            ]
            donut_options = {
                "tooltip": {
                    "trigger": "item",
                    "formatter": "{b}: <b>{c} units</b> ({d}%)",
                },
                "legend": {
                    "orient": "horizontal",
                    "bottom": "0%",
                    "textStyle": {"fontSize": 11, "color": "#475569"},
                },
                "color": ["#94a3b8", "#60a5fa", "#3b82f6", "#1d4ed8", "#1e40af", "#4338ca", "#3730a3"],
                "series": [
                    {
                        "name": "Rent Tier",
                        "type": "pie",
                        "radius": ["42%", "70%"],
                        "center": ["50%", "45%"],
                        "avoidLabelOverlap": True,
                        "itemStyle": {
                            "borderRadius": 5,
                            "borderColor": "#fff",
                            "borderWidth": 2,
                        },
                        "label": {"show": False},
                        "emphasis": {
                            "label": {"show": True, "fontSize": 12, "fontWeight": "bold"}
                        },
                        "data": pie_data,
                    }
                ],
            }
            st_echarts(donut_options, height="380px")
        else:
            st.info("No tier data available.")
        st.markdown("</div>", unsafe_allow_html=True)

    # 2. Bedroom Pricing Dynamics
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown('<div class="chart-card-title"> Rent Economics by Bedroom Count</div>', unsafe_allow_html=True)

    if not bed_summary.empty:
        col_b1, col_b2, col_b3, col_b4, col_b5 = st.columns(len(bed_summary))
        for idx, (_, row) in enumerate(bed_summary.iterrows()):
            with [col_b1, col_b2, col_b3, col_b4, col_b5][min(idx, 4)]:
                st.markdown(
                    f"""
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1rem; text-align: center;">
                        <div style="font-weight: 700; color: #013494; font-size: 1.05rem;">{row['Bedroom_Label']}</div>
                        <div style="font-size: 1.6rem; font-weight: 800; color: #1e293b; margin: 0.3rem 0;">${row['avg_rent']:,.0f}</div>
                        <div style="font-size: 0.8rem; color: #64748b;">Avg Monthly Rent</div>
                        <hr style="margin: 0.5rem 0; border: none; border-top: 1px dashed #cbd5e1;">
                        <div style="font-size: 0.82rem; color: #475569;">
                            <b>{int(row['unit_count']):,}</b> Units &bull; Median <b>${row['median_rent']:,.0f}</b>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    st.markdown("</div>", unsafe_allow_html=True)

    # 3. Unit-Level Explorer Table
    divider()
    section_header("Unit-Level Rent Explorer", "Search, sort, filter, and inspect individual unit rents and lease availability.")

    c_search, c_download = st.columns([3, 1])
    with c_search:
        unit_query = st.text_input(" Search Unit, Property or Unit Type", placeholder="e.g. 104casa, 1bds, Studio...", label_visibility="collapsed")

    display_units = filtered_units.copy()
    if unit_query:
        q = unit_query.lower().strip()
        display_units = display_units[
            display_units["Unit"].str.lower().str.contains(q) |
            display_units["Display_Property"].str.lower().str.contains(q) |
            display_units["Unit Type"].str.lower().str.contains(q)
        ]

    table_cols = [
        "Display_Property",
        "Unit",
        "Bedroom_Label",
        "Unit Type",
        "Rent_num",
        "Rent_Tier",
        "Display_Borough",
        "Display_Housing_Type",
    ]
    renamed_display = display_units[table_cols].rename(columns={
        "Display_Property": "Property / Project",
        "Unit": "Unit #",
        "Bedroom_Label": "Bedrooms",
        "Unit Type": "YARDI Unit Type",
        "Rent_num": "Monthly Rent ($)",
        "Rent_Tier": "Rent Tier",
        "Display_Borough": "Borough",
        "Display_Housing_Type": "Housing Type",
    })

    with c_download:
        csv_data = renamed_display.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=" Export Units CSV",
            data=csv_data,
            file_name="riseboro_units_rents.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.dataframe(
        renamed_display,
        column_config={
            "Monthly Rent ($)": st.column_config.NumberColumn(
                "Monthly Rent",
                format="$%.2f",
            ),
            "Property / Project": st.column_config.TextColumn("Property / Project", width="medium"),
            "Rent Tier": st.column_config.TextColumn("Rent Tier", width="small"),
        },
        hide_index=True,
        use_container_width=True,
        height=380,
    )


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2: CAPITAL STACK, SUBSIDIES & DEVELOPMENT
# ═════════════════════════════════════════════════════════════════════════════
with tab2:
    section_header(
        "Capital Stack & Development Finance",
        "Analyze portfolio development investments, construction budgets, LIHTC syndication, and permanent debt financing.",
    )

    proj_df = filtered_building.drop_duplicates(subset=["PROJECT_NAME"]).copy()
    proj_costed = proj_df[proj_df["TDC"] > 0].sort_values("TDC", ascending=False)

    col_c1, col_c2, col_c3 = st.columns(3)
    with col_c1:
        total_tdc = proj_costed["TDC"].sum()
        metric_card(
            label="Total Development Cost (TDC)",
            value=f"${total_tdc / 1e9:.2f}B" if total_tdc >= 1e9 else f"${total_tdc / 1e6:.1f}M",
            delta=f"{len(proj_costed)} Active/Completed Deals",
            delta_positive=True,
            
            show_arrow=False,
        )
    with col_c2:
        total_const = proj_costed["Construction_Cost"].sum()
        metric_card(
            label="Total Construction Budget",
            value=f"${total_const / 1e9:.2f}B" if total_const >= 1e9 else f"${total_const / 1e6:.1f}M",
            delta=f"{(total_const / max(total_tdc, 1)) * 100:.1f}% of Total Development",
            delta_positive=True,
            
            show_arrow=False,
        )
    with col_c3:
        avg_cost_unit = (total_tdc / max(proj_costed["Total_Units"].sum(), 1)) if not proj_costed.empty else 0
        metric_card(
            label="Avg. Development Cost / Unit",
            value=f"${avg_cost_unit:,.0f}",
            delta=f"{proj_costed['Total_Units'].sum():,} Project Units",
            delta_positive=True,
            
            show_arrow=False,
        )

    st.markdown("<div style='margin-bottom: 1rem;'></div>", unsafe_allow_html=True)

    # Capital Stack Breakdown Chart
    c_p1, c_p2 = st.columns([1.3, 1])
    with c_p1:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown('<div class="chart-card-title"> Largest Capital Development Projects ($ Millions)</div>', unsafe_allow_html=True)

        top_projects = proj_costed.head(8).iloc[::-1]
        if not top_projects.empty:
            tdc_millions = (top_projects["TDC"] / 1e6).round(1).tolist()
            const_millions = (top_projects["Construction_Cost"] / 1e6).round(1).tolist()
            proj_names = top_projects["PROJECT_NAME"].tolist()

            stack_options = {
                "tooltip": {
                    "trigger": "axis",
                    "axisPointer": {"type": "shadow"},
                    "formatter": "{b}<br/>Total Dev Cost: <b>${c0}M</b><br/>Construction Cost: <b>${c1}M</b>",
                },
                "legend": {"data": ["Total Development Cost", "Construction Cost"], "bottom": "0%"},
                "grid": {"left": "3%", "right": "4%", "bottom": "10%", "top": "3%", "containLabel": True},
                "xAxis": {"type": "value", "axisLabel": {"formatter": "${value}M"}},
                "yAxis": {"type": "category", "data": proj_names, "axisLabel": {"fontSize": 11}},
                "series": [
                    {
                        "name": "Total Development Cost",
                        "type": "bar",
                        "data": tdc_millions,
                        "itemStyle": {"color": PRIMARY, "borderRadius": [0, 4, 4, 0]},
                    },
                    {
                        "name": "Construction Cost",
                        "type": "bar",
                        "data": const_millions,
                        "itemStyle": {"color": "#60a5fa", "borderRadius": [0, 4, 4, 0]},
                    },
                ],
            }
            st_echarts(stack_options, height="380px")
        else:
            st.info("No project cost data available.")
        st.markdown("</div>", unsafe_allow_html=True)

    with c_p2:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown('<div class="chart-card-title"> Tax Credit & Subsidy Structure</div>', unsafe_allow_html=True)

        subsidy_counts = filtered_building["Subsidy_Category"].value_counts()
        if not subsidy_counts.empty:
            subsidy_pie = [{"name": str(k), "value": int(v)} for k, v in subsidy_counts.items() if v > 0]
            subsidy_options = {
                "tooltip": {"trigger": "item", "formatter": "{b}: <b>{c} properties</b> ({d}%)"},
                "legend": {"orient": "horizontal", "bottom": "0%", "textStyle": {"fontSize": 10}},
                "color": ["#013494", "#1e88e5", "#38bdf8", "#34d399", "#fbbf24", "#f87171", "#94a3b8"],
                "series": [
                    {
                        "name": "Subsidy Mix",
                        "type": "pie",
                        "radius": ["40%", "68%"],
                        "center": ["50%", "45%"],
                        "itemStyle": {"borderRadius": 5, "borderColor": "#fff", "borderWidth": 2},
                        "data": subsidy_pie,
                    }
                ],
            }
            st_echarts(subsidy_options, height="380px")
        st.markdown("</div>", unsafe_allow_html=True)

    # Lenders & Syndicators Table
    divider()
    section_header("Financing Partners & Permanent Lenders", "Overview of public agencies, private lenders, and tax credit syndicators.")

    c_lend1, c_lend2 = st.columns(2)
    with c_lend1:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown('<div class="chart-card-title"> Permanent Lenders</div>', unsafe_allow_html=True)
        lender_counts = filtered_building[filtered_building["Lender"] != "Not Specified"]["Lender"].value_counts().reset_index()
        lender_counts.columns = ["Lender Entity", "Project Count"]
        st.dataframe(lender_counts, hide_index=True, use_container_width=True, height=240)
        st.markdown("</div>", unsafe_allow_html=True)

    with c_lend2:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown('<div class="chart-card-title"> LIHTC Syndicators & Partners</div>', unsafe_allow_html=True)
        synd_counts = filtered_building[filtered_building["Syndicator"] != "Not Specified"]["Syndicator"].value_counts().reset_index()
        synd_counts.columns = ["Syndicator / Equity Partner", "Project Count"]
        st.dataframe(synd_counts, hide_index=True, use_container_width=True, height=240)
        st.markdown("</div>", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3: MAINTENANCE OPEX & COST DRAG
# ═════════════════════════════════════════════════════════════════════════════
with tab3:
    section_header(
        "Maintenance OpEx & Revenue Drag",
        "Synthesize work order repair costs against Gross Potential Rent to quantify operational drag and trade expenses.",
    )

    if wo_df is not None and not wo_df.empty:
        drag_summary, cat_summary, opex_kpis = calculate_maintenance_drag(wo_df, filtered_units)

        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1:
            metric_card(
                label="Total Work Order Cost",
                value=f"${opex_kpis.get('total_wo_spend', 0):,.0f}",
                delta=f"{opex_kpis.get('total_wos_costed', 0):,} costed WOs",
                delta_positive=True,
                
                show_arrow=False,
            )
        with col_m2:
            ann_wo = opex_kpis.get("annualized_wo_spend", 0)
            metric_card(
                label="Annual Maintenance Run-Rate",
                value=f"${ann_wo:,.0f}/yr",
                delta=f"Based on {opex_kpis.get('years_span', 1):.1f} yr history",
                delta_positive=True,
                
                show_arrow=False,
            )
        with col_m3:
            drag_pct = opex_kpis.get("portfolio_maintenance_drag_pct", 0)
            metric_card(
                label="Portfolio Maintenance Drag",
                value=f"{drag_pct:.2f}%",
                delta="WO Cost % of Rent Roll",
                delta_positive=drag_pct < 10.0,
                
                show_arrow=False,
            )
        with col_m4:
            avg_wo_cost = opex_kpis.get("avg_cost_per_wo", 0)
            metric_card(
                label="Avg Cost / Work Order",
                value=f"${avg_wo_cost:,.2f}",
                delta="Direct materials/labor",
                delta_positive=True,
                
                show_arrow=False,
            )

        st.markdown("<div style='margin-bottom: 1.25rem;'></div>", unsafe_allow_html=True)

        # 1. Maintenance Drag by Property & Category Spend
        c_drag_l, c_drag_r = st.columns([1.3, 1])

        with c_drag_l:
            st.markdown('<div class="chart-card">', unsafe_allow_html=True)
            st.markdown('<div class="chart-card-title"> Maintenance Drag (% of Gross Rent Roll) by Property</div>', unsafe_allow_html=True)

            top_drag = drag_summary[drag_summary["annualized_wo_spend"] > 0].head(10).iloc[::-1]
            if not top_drag.empty:
                drag_options = {
                    "tooltip": {
                        "trigger": "axis",
                        "axisPointer": {"type": "shadow"},
                        "formatter": "{b}<br/>Maintenance Drag: <b>{c}% of Rent Roll</b>",
                    },
                    "grid": {"left": "3%", "right": "6%", "bottom": "3%", "top": "3%", "containLabel": True},
                    "xAxis": {
                        "type": "value",
                        "axisLabel": {"formatter": "{value}%"},
                        "splitLine": {"lineStyle": {"color": "#f1f5f9"}},
                    },
                    "yAxis": {
                        "type": "category",
                        "data": top_drag["Display_Property"].tolist(),
                        "axisLabel": {"fontSize": 11},
                    },
                    "series": [
                        {
                            "name": "Maintenance Drag %",
                            "type": "bar",
                            "data": top_drag["maintenance_drag_pct"].round(2).tolist(),
                            "itemStyle": {
                                "color": "#e53935",
                                "borderRadius": [0, 6, 6, 0],
                            },
                        }
                    ],
                }
                st_echarts(drag_options, height="360px")
            else:
                st.info("No work orders matched to selected properties.")
            st.markdown("</div>", unsafe_allow_html=True)

        with c_drag_r:
            st.markdown('<div class="chart-card">', unsafe_allow_html=True)
            st.markdown('<div class="chart-card-title"> Maintenance Spend by Trade / Category</div>', unsafe_allow_html=True)

            if not cat_summary.empty:
                cat_pie = [
                    {"name": str(row.iloc[0]), "value": round(float(row["total_spend"]), 2)}
                    for _, row in cat_summary.head(8).iterrows()
                    if row["total_spend"] > 0
                ]
                cat_options = {
                    "tooltip": {"trigger": "item", "formatter": "{b}: <b>${c:,.0f}</b> ({d}%)"},
                    "legend": {"orient": "horizontal", "bottom": "0%", "textStyle": {"fontSize": 10}},
                    "color": ["#013494", "#e53935", "#fb8c00", "#1e88e5", "#43a047", "#8e24aa", "#00acc1", "#94a3b8"],
                    "series": [
                        {
                            "name": "Category Spend",
                            "type": "pie",
                            "radius": ["38%", "66%"],
                            "center": ["50%", "45%"],
                            "itemStyle": {"borderRadius": 5, "borderColor": "#fff", "borderWidth": 2},
                            "data": cat_pie,
                        }
                    ],
                }
                st_echarts(cat_options, height="360px")
            else:
                st.info("No category spend data available.")
            st.markdown("</div>", unsafe_allow_html=True)

        # 2. Detailed Property OpEx Breakdown Table
        divider()
        section_header("Property OpEx & Drag Summary Table", "Compare annual revenue with repair expenditures across the portfolio.")

        prop_drag_table = drag_summary[[
            "Display_Property",
            "Display_Borough",
            "total_units",
            "annual_rent_roll",
            "annualized_wo_spend",
            "maintenance_drag_pct",
            "wo_spend_per_unit",
            "wo_count",
        ]].rename(columns={
            "Display_Property": "Property",
            "Display_Borough": "Borough",
            "total_units": "Units",
            "annual_rent_roll": "Annual Rent Roll",
            "annualized_wo_spend": "Ann. Maint. Spend",
            "maintenance_drag_pct": "Maint. Drag %",
            "wo_spend_per_unit": "Spend / Unit / Yr",
            "wo_count": "Total WOs",
        })

        st.dataframe(
            prop_drag_table,
            column_config={
                "Annual Rent Roll": st.column_config.NumberColumn("Annual Rent Roll", format="$%d"),
                "Ann. Maint. Spend": st.column_config.NumberColumn("Ann. Maint. Spend", format="$%d"),
                "Maint. Drag %": st.column_config.NumberColumn("Maint. Drag %", format="%.2f%%"),
                "Spend / Unit / Yr": st.column_config.NumberColumn("Spend / Unit / Yr", format="$%d"),
                "Total WOs": st.column_config.NumberColumn("Total WOs", format="%d"),
            },
            hide_index=True,
            use_container_width=True,
            height=340,
        )

    else:
        # Zero-state guidance for Work Order upload
        st.markdown(
            """
            <div style="background: linear-gradient(135deg, #f0f7ff 0%, #e8f0fe 100%);
                        border: 2px dashed #013494; border-radius: 16px; padding: 2.5rem; text-align: center; margin: 1rem 0;">
                <div style="font-size: 2.5rem; color: #013494; margin-bottom: 0.5rem;"></div>
                <h3 style="color: #013494; font-weight: 700; margin-bottom: 0.5rem;">Upload Work Orders to Enable Maintenance Drag Analytics</h3>
                <p style="color: #475569; max-width: 600px; margin: 0 auto 1.5rem auto; font-size: 0.95rem;">
                    When you upload work orders with material and labor pricing (<code>Unit Price</code>, <code>Quantity</code>, <code>Total</code>),
                    this dashboard automatically computes Net Operational Yield, Maintenance Drag (% of Rent Roll), and trade-level expense distributions.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        c1, c2, c3 = st.columns([1, 1.5, 1])
        with c2:
            st.page_link("pages/upload.py", label="Go to Upload Page")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 4: COMMERCIAL PORTFOLIO & ASSET VINTAGE
# ═════════════════════════════════════════════════════════════════════════════
with tab4:
    section_header(
        "Commercial Portfolio & Asset Vintage",
        "Explore community commercial spaces, leased square footage, and capital rehabilitation history.",
    )

    comm_df = filtered_building[filtered_building["Has_Commercial"]].copy()

    col_v1, col_v2, col_v3 = st.columns(3)
    with col_v1:
        total_sqft = comm_df["Commercial_SqFt"].sum()
        metric_card(
            label="Total Leased Commercial Space",
            value=f"{total_sqft:,.0f} SqFt",
            delta=f"{len(comm_df)} Commercial Units",
            delta_positive=True,
            
            show_arrow=False,
        )
    with col_v2:
        comm_props = comm_df["PROJECT_NAME"].nunique()
        metric_card(
            label="Properties with Commercial / Retail",
            value=f"{comm_props}",
            delta="Community & retail facilities",
            delta_positive=True,
            
            show_arrow=False,
        )
    with col_v3:
        senior_centers = comm_df["Senior Center name_program"].dropna().count() if "Senior Center name_program" in comm_df.columns else 0
        metric_card(
            label="Community & Senior Service Sites",
            value=f"{senior_centers}",
            delta="Dedicated on-site programs",
            delta_positive=True,
            
            show_arrow=False,
        )

    st.markdown("<div style='margin-bottom: 1rem;'></div>", unsafe_allow_html=True)

    # 1. Commercial Unit Listings Table
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown('<div class="chart-card-title"> Commercial & Community Spaces Directory</div>', unsafe_allow_html=True)

    comm_display_cols = [
        "PLACE_NAME",
        "PROJECT_NAME",
        "ADDRESS",
        "Permitted Use_commercial",
        "Actual Use_commercial",
        "Tenant's Name or Leasee_commercial",
        "Comm SqFt Leased_commercial",
        "Lessee Type_commercial",
    ]
    existing_comm_cols = [c for c in comm_display_cols if c in comm_df.columns]
    comm_table = comm_df[existing_comm_cols].dropna(subset=["Permitted Use_commercial", "Actual Use_commercial", "Tenant's Name or Leasee_commercial"], how="all")

    st.dataframe(
        comm_table.rename(columns={
            "PLACE_NAME": "Facility / Site",
            "PROJECT_NAME": "Project",
            "ADDRESS": "Address",
            "Permitted Use_commercial": "Permitted Use",
            "Actual Use_commercial": "Actual Use",
            "Tenant's Name or Leasee_commercial": "Tenant / Lessee",
            "Comm SqFt Leased_commercial": "Leased SqFt",
            "Lessee Type_commercial": "Lessee Type",
        }),
        hide_index=True,
        use_container_width=True,
        height=320,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    # 2. Rehab Vintage Timeline
    divider()
    section_header("Asset Vintage & Capital Rehabilitation", "Chronological distribution of original construction and latest rehabilitation.")

    if not renovations_df.empty:
        ren_valid = renovations_df.dropna(subset=["Most_Recent_Rehab"]).sort_values("Most_Recent_Rehab")
        rehab_by_year = ren_valid["Most_Recent_Rehab"].astype(int).value_counts().sort_index()

        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown('<div class="chart-card-title"> Rehabilitation Vintage by Year</div>', unsafe_allow_html=True)

        rehab_options = {
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "grid": {"left": "3%", "right": "3%", "bottom": "3%", "top": "5%", "containLabel": True},
            "xAxis": {"type": "category", "data": [str(y) for y in rehab_by_year.index]},
            "yAxis": {"type": "value", "name": "Properties Rehabbed"},
            "series": [
                {
                    "name": "Rehabbed Properties",
                    "type": "bar",
                    "data": rehab_by_year.values.tolist(),
                    "itemStyle": {"color": PRIMARY, "borderRadius": [4, 4, 0, 0]},
                }
            ],
        }
        st_echarts(rehab_options, height="280px")
        st.markdown("</div>", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 5: HPD MUNICIPAL FEE CHARGES & COMPLIANCE
# ═════════════════════════════════════════════════════════════════════════════
with tab5:
    section_header(
        "HPD Municipal Fee Charges & Compliance",
        "Track building-level municipal inspection fees, heat/hot water charges, and Department of Finance tax transfers.",
    )

    fee_kpis = calculate_hpd_fee_kpis(filtered_charges, filtered_building)

    # ── KPI Cards ────────────────────────────────────────────────────────
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1:
        metric_card(
            label="Total HPD Charges Assessed",
            value=f"{fee_kpis['total_charges']:,}",
            delta=f"${fee_kpis['total_fee_amount']:,.0f} Est. Total Liability",
            delta_positive=True,
            show_arrow=False,
        )
    with col_f2:
        affected_pct = (
            (fee_kpis["affected_properties"] / max(filtered_building["PROJECT_NAME"].nunique(), 1)) * 100.0
            if not filtered_building.empty else 0.0
        )
        metric_card(
            label="Properties with Assessed Fees",
            value=f"{fee_kpis['affected_properties']}",
            delta=f"{affected_pct:.1f}% of Filtered Portfolio",
            delta_positive=True,
            show_arrow=False,
        )
    with col_f3:
        metric_card(
            label="Transferred to DOF (Tax Liens)",
            value=f"{fee_kpis['dof_transferred_count']:,}",
            delta=f"{fee_kpis['dof_transfer_pct']:.1f}% Transferred to Property Tax",
            delta_positive=(fee_kpis["dof_transferred_count"] == 0),
            show_arrow=False,
        )
    with col_f4:
        metric_card(
            label="Primary Infraction Category",
            value=f"{fee_kpis['top_fee_type']}",
            delta=f"Latest Assessed: {fee_kpis['latest_fee_date']}",
            delta_positive=True,
            show_arrow=False,
        )

    st.markdown("<div style='margin-bottom: 1.25rem;'></div>", unsafe_allow_html=True)

    if filtered_charges.empty:
        st.info("No municipal fee charge records found for the selected filter criteria.")
    else:

        # ── Visualizations Row 1: Top Buildings & Fee Composition ────────────
        b_summary = get_building_fee_summary(filtered_charges)
        fee_dist = get_fee_type_distribution(filtered_charges)

        c_top_b, c_pie_fee = st.columns([1.4, 1])

        with c_top_b:
            st.markdown('<div class="chart-card">', unsafe_allow_html=True)
            st.markdown('<div class="chart-card-title"> Top Properties by Assessed Fee Charges</div>', unsafe_allow_html=True)

            top_10_fee_bldgs = b_summary.head(10).iloc[::-1]
            if not top_10_fee_bldgs.empty:
                bldg_labels = [
                    f"{row['Display_Property']} ({row['Building_Address']})" if row['Building_Address'] != row['Display_Property'] else row['Display_Property']
                    for _, row in top_10_fee_bldgs.iterrows()
                ]
                bldg_charges = top_10_fee_bldgs["total_charges"].tolist()
                bldg_liabilities = top_10_fee_bldgs["total_fee_liability"].tolist()

                bar_chart_options = {
                    "tooltip": {
                        "trigger": "axis",
                        "axisPointer": {"type": "shadow"},
                        "formatter": "{b}<br/>Total Charges: <b>{c} fees</b>",
                    },
                    "grid": {"left": "3%", "right": "6%", "bottom": "3%", "top": "3%", "containLabel": True},
                    "xAxis": {
                        "type": "value",
                        "axisLabel": {"formatter": "{value}"},
                        "splitLine": {"lineStyle": {"color": "#f1f5f9"}},
                    },
                    "yAxis": {
                        "type": "category",
                        "data": bldg_labels,
                        "axisLabel": {"color": "#334155", "fontSize": 11},
                    },
                    "series": [
                        {
                            "name": "Fee Charges",
                            "type": "bar",
                            "data": bldg_charges,
                            "itemStyle": {
                                "color": {
                                    "type": "linear",
                                    "x": 0, "y": 0, "x2": 1, "y2": 0,
                                    "colorStops": [
                                        {"offset": 0, "color": "#e53935"},
                                        {"offset": 1, "color": "#fb8c00"},
                                    ],
                                },
                                "borderRadius": [0, 6, 6, 0],
                            },
                        }
                    ],
                }
                st_echarts(bar_chart_options, height="380px")
            else:
                st.info("No building charge data available.")
            st.markdown("</div>", unsafe_allow_html=True)

        with c_pie_fee:
            st.markdown('<div class="chart-card">', unsafe_allow_html=True)
            st.markdown('<div class="chart-card-title"> Fee Breakdown by Infraction Type</div>', unsafe_allow_html=True)

            if not fee_dist.empty:
                pie_fee_data = [
                    {"name": row["Fee_Type"], "value": int(row["charge_count"])}
                    for _, row in fee_dist.iterrows()
                    if row["charge_count"] > 0
                ]
                fee_donut_options = {
                    "tooltip": {
                        "trigger": "item",
                        "formatter": "{b}: <b>{c} charges</b> ({d}%)",
                    },
                    "legend": {
                        "orient": "horizontal",
                        "bottom": "0%",
                        "textStyle": {"fontSize": 10, "color": "#475569"},
                    },
                    "color": ["#013494", "#e53935", "#fb8c00", "#1e88e5", "#43a047", "#8e24aa", "#00acc1"],
                    "series": [
                        {
                            "name": "Fee Category",
                            "type": "pie",
                            "radius": ["40%", "68%"],
                            "center": ["50%", "45%"],
                            "itemStyle": {
                                "borderRadius": 5,
                                "borderColor": "#fff",
                                "borderWidth": 2,
                            },
                            "data": pie_fee_data,
                        }
                    ],
                }
                st_echarts(fee_donut_options, height="380px")
            else:
                st.info("No fee category data available.")
            st.markdown("</div>", unsafe_allow_html=True)

        # ── Visualizations Row 2: Annual Trend & Source Document ─────────────
        annual_trend = get_annual_fee_trend(filtered_charges)
        source_dist = get_fee_source_distribution(filtered_charges)

        c_trend, c_src = st.columns([1.4, 1])

        with c_trend:
            st.markdown('<div class="chart-card">', unsafe_allow_html=True)
            st.markdown('<div class="chart-card-title"> Annual Fee Issuance & DOF Transfer Trend</div>', unsafe_allow_html=True)

            if not annual_trend.empty:
                years_list = [str(y) for y in annual_trend["Year_Issued"].tolist()]
                total_series = annual_trend["charge_count"].tolist()
                dof_series = annual_trend["dof_transferred"].tolist()

                trend_options = {
                    "tooltip": {
                        "trigger": "axis",
                        "axisPointer": {"type": "shadow"},
                        "formatter": "{b}<br/>Assessed Charges: <b>{c0}</b><br/>Transferred to DOF: <b>{c1}</b>",
                    },
                    "legend": {"data": ["Total Assessed Fees", "Transferred to DOF (Tax Billed)"], "bottom": "0%"},
                    "grid": {"left": "3%", "right": "4%", "bottom": "12%", "top": "5%", "containLabel": True},
                    "xAxis": {"type": "category", "data": years_list, "axisLabel": {"color": "#475569"}},
                    "yAxis": {"type": "value", "name": "Charges Count", "splitLine": {"lineStyle": {"color": "#f1f5f9"}}},
                    "series": [
                        {
                            "name": "Total Assessed Fees",
                            "type": "bar",
                            "data": total_series,
                            "itemStyle": {"color": PRIMARY, "borderRadius": [4, 4, 0, 0]},
                        },
                        {
                            "name": "Transferred to DOF (Tax Billed)",
                            "type": "bar",
                            "data": dof_series,
                            "itemStyle": {"color": "#60a5fa", "borderRadius": [4, 4, 0, 0]},
                        },
                    ],
                }
                st_echarts(trend_options, height="320px")
            else:
                st.info("No annual trend data available.")
            st.markdown("</div>", unsafe_allow_html=True)

        with c_src:
            st.markdown('<div class="chart-card">', unsafe_allow_html=True)
            st.markdown('<div class="chart-card-title"> Fee Trigger Origin / Document Source</div>', unsafe_allow_html=True)

            if not source_dist.empty:
                src_pie_data = [
                    {"name": row["Source_Type"], "value": int(row["charge_count"])}
                    for _, row in source_dist.iterrows()
                    if row["charge_count"] > 0
                ]
                src_donut_options = {
                    "tooltip": {
                        "trigger": "item",
                        "formatter": "{b}: <b>{c} charges</b> ({d}%)",
                    },
                    "legend": {
                        "orient": "horizontal",
                        "bottom": "0%",
                        "textStyle": {"fontSize": 10, "color": "#475569"},
                    },
                    "color": ["#1e88e5", "#fb8c00", "#43a047", "#8e24aa", "#94a3b8"],
                    "series": [
                        {
                            "name": "Trigger Source",
                            "type": "pie",
                            "radius": ["38%", "66%"],
                            "center": ["50%", "45%"],
                            "itemStyle": {
                                "borderRadius": 5,
                                "borderColor": "#fff",
                                "borderWidth": 2,
                            },
                            "data": src_pie_data,
                        }
                    ],
                }
                st_echarts(src_donut_options, height="320px")
            else:
                st.info("No trigger source data available.")
            st.markdown("</div>", unsafe_allow_html=True)

        # ── Building-Level Fee Summary Table ─────────────────────────────────
        divider()
        section_header(
            "Building-Level Municipal Fee Compliance Directory",
            "Comprehensive breakdown of fee infractions, DOF transfer rates, and estimated liabilities per building.",
        )

        display_b_summary = b_summary.copy()
        display_b_summary["latest_fee_formatted"] = display_b_summary["latest_fee_date"].dt.strftime("%b %d, %Y")

        b_table = display_b_summary[[
            "Display_Property",
            "Building_Address",
            "Display_Borough",
            "bbl",
            "total_charges",
            "total_fee_liability",
            "dof_transferred",
            "dof_transfer_pct",
            "top_infraction",
            "latest_fee_formatted",
        ]].rename(columns={
            "Display_Property": "Property / Project",
            "Building_Address": "Street Address",
            "Display_Borough": "Borough",
            "bbl": "BBL",
            "total_charges": "Total Charges",
            "total_fee_liability": "Est. Liability ($)",
            "dof_transferred": "DOF Transferred",
            "dof_transfer_pct": "DOF Transfer %",
            "top_infraction": "Primary Infraction",
            "latest_fee_formatted": "Latest Fee Date",
        })

        st.dataframe(
            b_table,
            column_config={
                "Property / Project": st.column_config.TextColumn("Property / Project", width="medium"),
                "Street Address": st.column_config.TextColumn("Street Address", width="medium"),
                "Total Charges": st.column_config.NumberColumn("Total Charges", format="%d"),
                "Est. Liability ($)": st.column_config.NumberColumn("Est. Liability", format="$%d"),
                "DOF Transferred": st.column_config.NumberColumn("DOF Transferred", format="%d"),
                "DOF Transfer %": st.column_config.NumberColumn("DOF Transfer %", format="%.1f%%"),
                "Primary Infraction": st.column_config.TextColumn("Primary Infraction", width="medium"),
                "Latest Fee Date": st.column_config.TextColumn("Latest Fee Date", width="small"),
            },
            hide_index=True,
            use_container_width=True,
            height=340,
        )

        # ── Individual Charges Explorer ──────────────────────────────────────
        divider()
        section_header(
            "Individual Charge Record Explorer",
            "Search, filter, and inspect specific municipal charge citations, issue dates, and DOF billing transfers.",
        )

        c_search_fee, c_type_fee, c_dof_toggle, c_dl_fee = st.columns([2, 1.5, 1, 1])

        with c_search_fee:
            charge_query = st.text_input(
                "Search Charge Records",
                placeholder="Search by Address, Property, BBL, or Fee ID...",
                label_visibility="collapsed",
            )

        with c_type_fee:
            available_types = ["All Fee Types"] + sorted(filtered_charges["Fee_Type"].dropna().unique().tolist())
            selected_type = st.selectbox("Filter Fee Type", options=available_types, label_visibility="collapsed")

        with c_dof_toggle:
            dof_only = st.toggle("DOF Only", value=False, help="Show only fees transferred to Dept of Finance for tax billing")

        display_charges = filtered_charges.copy()
        if charge_query:
            cq = charge_query.lower().strip()
            display_charges = display_charges[
                display_charges["Building_Address"].str.lower().str.contains(cq)
                | display_charges["Display_Property"].str.lower().str.contains(cq)
                | display_charges["bbl"].str.contains(cq)
                | display_charges["feeid"].astype(str).str.contains(cq)
            ]

        if selected_type != "All Fee Types":
            display_charges = display_charges[display_charges["Fee_Type"] == selected_type]

        if dof_only:
            display_charges = display_charges[display_charges["Transferred_To_DOF"]]

        display_charges_table = display_charges[[
            "feeid",
            "Display_Property",
            "Building_Address",
            "Display_Borough",
            "bbl",
            "Fee_Type",
            "Source_Type",
            "Estimated_Fee_Amount",
            "feeissueddate_dt",
            "doftransferdate_dt",
            "lifecycle",
        ]].copy()

        display_charges_table["Issued_Date_Str"] = display_charges_table["feeissueddate_dt"].dt.strftime("%Y-%m-%d")
        display_charges_table["DOF_Date_Str"] = display_charges_table["doftransferdate_dt"].dt.strftime("%Y-%m-%d").fillna("Pending / Not Transferred")

        renamed_charges = display_charges_table[[
            "feeid",
            "Display_Property",
            "Building_Address",
            "Display_Borough",
            "bbl",
            "Fee_Type",
            "Source_Type",
            "Estimated_Fee_Amount",
            "Issued_Date_Str",
            "DOF_Date_Str",
            "lifecycle",
        ]].rename(columns={
            "feeid": "Fee ID",
            "Display_Property": "Property / Project",
            "Building_Address": "Street Address",
            "Display_Borough": "Borough",
            "bbl": "BBL",
            "Fee_Type": "Fee Infraction Type",
            "Source_Type": "Source Document",
            "Estimated_Fee_Amount": "Est. Fee ($)",
            "Issued_Date_Str": "Fee Issued Date",
            "DOF_Date_Str": "DOF Transfer Date",
            "lifecycle": "Building Status",
        })

        with c_dl_fee:
            csv_fee_data = renamed_charges.to_csv(index=False).encode("utf-8")
            st.download_button(
                label=" Export CSV",
                data=csv_fee_data,
                file_name="riseboro_hpd_fee_charges.csv",
                mime="text/csv",
                use_container_width=True,
            )

        st.dataframe(
            renamed_charges,
            column_config={
                "Fee ID": st.column_config.TextColumn("Fee ID", width="small"),
                "Est. Fee ($)": st.column_config.NumberColumn("Est. Fee ($)", format="$%.2f"),
                "Property / Project": st.column_config.TextColumn("Property / Project", width="medium"),
                "Street Address": st.column_config.TextColumn("Street Address", width="medium"),
                "Fee Infraction Type": st.column_config.TextColumn("Fee Type", width="medium"),
                "Source Document": st.column_config.TextColumn("Source", width="small"),
                "Fee Issued Date": st.column_config.TextColumn("Issued Date", width="small"),
                "DOF Transfer Date": st.column_config.TextColumn("DOF Billed", width="small"),
            },
            hide_index=True,
            use_container_width=True,
            height=380,
        )

        # ── Municipal Regulatory Guidance Callout ────────────────────────────
        st.markdown(
            """
            <div class="highlight-box">
                <div style="font-weight: 700; color: #013494; font-size: 1rem; margin-bottom: 0.35rem;">
                     NYC Housing Maintenance Code & DOF Billing Notice
                </div>
                <div style="font-size: 0.88rem; color: #334155; line-height: 1.5;">
                    <b>Statutory Assessment Rules:</b> Pursuant to NYC Administrative Code § 27-2115(k)(1), HPD assesses a $200 inspection fee when a reinspection confirms an open hazardous (Class B) or immediately hazardous (Class C) violation, heat/hot water failure, or Alternative Enforcement Program (AEP) complaint inspection.
                    <br/><br/>
                    <b>Department of Finance (DOF) Transfer:</b> Unpaid HPD charges are routinely transferred to the NYC Department of Finance (DOF account types 236, 240, 243) and added directly to the property's quarterly property tax statement. If left unpaid, these charges can accrue interest and constitute a municipal lien against the property.
                    <br/><br/>
                    <b>Dispute & Abatement:</b> Property managers can contest or request an administrative review of inspection fees within 30 days of issuance by filing an HPD Fee Abatement Request or verifying timely violation certification prior to the inspection date.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

