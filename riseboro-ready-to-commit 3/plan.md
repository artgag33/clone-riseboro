# Implementation Plan: Financials-Focused Dashboard

Create a dedicated, interactive **Financials Dashboard** for RiseBoro that analyzes portfolio revenue economics, capital development stacks, subsidy structures, and maintenance operational expense (OpEx) drag using the existing datasets in the repository.

---

## User Review Required

> [!IMPORTANT]
> **Data Sources & Integration Strategy:**
> 1. **Baseline Financials (Instant, No Upload Required):** The dashboard will immediately load and display portfolio financials from [data/units_rents.csv](file:///Users/leoledlow/Projects/riseboro_streamlit/data/units_rents.csv) (3,135 units, ~$55.6M annualized rent roll), [data/building_codes.csv](file:///Users/leoledlow/Projects/riseboro_streamlit/data/building_codes.csv) (>$5.5B in Total Development Cost across 145+ projects, LIHTC syndicators, permanent lenders, ownership stakes, commercial leases), and [data/renovations.csv](file:///Users/leoledlow/Projects/riseboro_streamlit/data/renovations.csv).
> 2. **Maintenance Cost / OpEx Drag (Unlocked with Work Orders):** When work orders are uploaded via [pages/upload.py](file:///Users/leoledlow/Projects/riseboro_streamlit/pages/upload.py) (`st.session_state.wo_df`), the dashboard will seamlessly integrate `Unit Price`, `Quantity`, and `Total` to calculate maintenance costs vs. rent roll per property and trade. If no WO data is uploaded, helpful guidance and fallback summaries will be shown.

> [!NOTE]
> **Multi-Page Navigation:**
> The new dashboard will be integrated as a dedicated page in [app.py](file:///Users/leoledlow/Projects/riseboro_streamlit/app.py) (`pages/financials.py`) alongside the Operations Dashboard and the Upload page.

---

## Open Questions

1. **Rent Roll Baseline Scope:** In `units_rents.csv`, ~136 units have `$0.00` recorded rent (often representing subsidized, voucher, or non-revenue units). Should our default average rent calculations exclude `$0` units, or do you prefer showing both Gross Potential Rent (market/standard) and Net Collected / Subsidized distributions? *(Recommendation: We will calculate metrics both ways with a toggle or clear subtitle breakdown).*
2. **Maintenance Drag Period:** For the OpEx vs. Revenue analysis (WO Cost / Annual Rent Roll), should we annualize the WO spend based on the date range selected in the filter, or compare total historical WO spend against current annual rent roll? *(Recommendation: Provide an annualized repair rate so it scales proportionally).*

---

## Proposed Changes

### Core Financial Processing Module

#### [NEW] [src/financials.py](file:///Users/leoledlow/Projects/riseboro_streamlit/src/financials.py)
A clean, modular data processing and aggregation service:
- `load_units_rents()`: Clean `Rent` currency strings into numeric floats, standardize unit types, extract bedroom counts, and join with property metadata.
- `load_building_financials()`: Clean and normalize `Total Development Cost_PROJECT_2`, `Total Construction Cost_PROJECT_2`, LIHTC syndicators, permanent lenders, tax credit structures (4% / 9%), ownership percentages, and commercial spaces.
- `calculate_portfolio_kpis()`: Gross Potential Rent (Monthly & Annualized), Active Unit Count, Average Rent per Bedroom, Total Development Cost, Total Construction Cost, and Total Commercial SqFt.
- `calculate_property_rent_summary()`: Aggregated rent roll table per property/project with unit counts, average rent, and bedroom distributions.
- `calculate_maintenance_drag(wo_df, rent_summary)`: Computes total maintenance spend by property and category, repair cost per unit, and maintenance spend as a percentage of gross rent roll.

---

### Dashboard User Interface

#### [NEW] [pages/financials.py](file:///Users/leoledlow/Projects/riseboro_streamlit/pages/financials.py)
A full-featured Streamlit page styled with RiseBoro's design system:

1. **Hero & Top-Level KPI Bar:**
   - **Annualized Gross Rent Roll:** `~$55.56M`
   - **Monthly Rent Roll:** `~$4.63M`
   - **Active Residential Units:** `3,135` across 57 properties
   - **Avg. Monthly Rent / Unit:** `$1,544` (excluding $0/subsidized)
   - **Total Portfolio Development Cost:** `~$5.55B` (across 145+ projects)
   - **Maintenance OpEx / Drag:** *(Dynamic when WO uploaded)*

2. **Global Sidebar Filters:**
   - Filter by Borough (Brooklyn, Queens, Bronx, Manhattan)
   - Filter by Housing Type (Multi-Family, Senior, Supportive, etc.)
   - Filter by Property / Project
   - Filter by Bedroom Count (Studio, 1BR, 2BR, 3BR, 4BR)

3. **Tab 1: Rent Roll & Revenue Economics (`:material/attach_money:`)**
   - **Top Properties by Rent Roll:** Interactive horizontal bar chart comparing the top revenue-generating properties (Sumner, Baisley, Hillside, 326 Rockaway, 1601 DeKalb, etc.).
   - **Rent Distribution & Tiers:** Histogram/tier chart (`<$500`, `$500–$1,000`, `$1,000–$1,500`, `$1,500–$2,000`, `$2,000–$2,500`, `$2,500+`).
   - **Bedroom Pricing Dynamics:** Box plot / bar breakdown of average rent and rent-per-bedroom.
   - **Unit-Level Rent Explorer:** Searchable, paginated data table with column formatting (`$%.2f`), bedroom badges, and CSV export.

4. **Tab 2: Capital Stack, Subsidies & Development (`:material/account_balance:`)**
   - **Development & Construction Capital:** Project-by-project breakdown of Total Development Cost (TDC) vs. Construction Cost.
   - **Tax Credit & Subsidy Structure:** Distribution of 4% LIHTC, 9% LIHTC, Section 8, ESSHI, NYC 15/15, and HPD/HCR programs.
   - **Lenders & Syndicators:** Breakdown of public/private permanent lenders (HPD, HDC, HCR, Goldman Sachs, BofA, Webster, Merchants, Freddie TEL) and LIHTC syndicators (NEF, Redstone, Wells Fargo, SunAmerica, Camber).
   - **RiseBoro Ownership & Joint Venture Stakes:** Distribution of ownership % across entities.

5. **Tab 3: Maintenance OpEx & Cost Drag (`:material/build:`)**
   - *Active when work orders are present in `session_state.wo_df`*
   - **Maintenance Spend by Trade / Category:** Work order cost breakdown by trade (Plumbing, Electrical, HVAC, Extermination, Carpentry, etc.).
   - **Maintenance Drag Ranking:** Repair spend as a percentage of property annual rent roll (identifying buildings where repair costs erode revenue).
   - **High-Cost Unit Outliers:** Top 15 units with highest repair expenses and average cost per work order.
   - **Zero-State Callout:** If work orders have not been uploaded yet, shows an informative callout directing users to the upload page.

6. **Tab 4: Commercial Portfolio & Vintage (`:material/store:`)**
   - **Commercial Space Footprint:** Leased sqft by use type (Retail, Community, Healthcare, Supermarket, Safe House, Urban Farm).
   - **Rehab Vintage & Capital Life:** Timeline of construction completion dates and most recent rehabilitation years from `renovations.csv`.

---

### App Navigation Update

#### [MODIFY] [app.py](file:///Users/leoledlow/Projects/riseboro_streamlit/app.py)
Register `pages/financials.py` in `st.navigation`:
- Add `st.Page("pages/financials.py", title="Financials", icon=":material/payments:")`

---

## Verification Plan

### Automated Tests
- Test data loading, cleaning, and currency parsing in `src/financials.py` against all three CSV files.
```bash
./venv/bin/python -c "from src.financials import load_units_rents, load_building_financials; ur = load_units_rents(); bf = load_building_financials(); print('Data loaded:', len(ur), len(bf))"
```

### Manual Verification
1. Launch Streamlit application: `streamlit run app.py`
2. Navigate to the new **Financials** page from the sidebar.
3. Verify KPI cards render accurate portfolio totals (~$55.6M annual rent roll, ~$5.55B TDC).
4. Test filtering by borough, property, and bedroom count; verify charts and tables react dynamically.
5. Upload a work order CSV in the Upload tab, then navigate back to Financials Tab 3 ("Maintenance OpEx & Cost Drag") to confirm maintenance drag and category spend populate seamlessly.
