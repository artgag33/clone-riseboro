"""
src/helpers.py
--------------
Helper functions for classifying work order descriptions and analyzing seasonal trends.
"""

import pandas as pd


def classify_issue(desc: str) -> str | None:
    """
    Classify a work order description into one of five categories:
    - Elevators
    - Hot Water
    - Heat
    - Leaks
    - Roof
    Returns None if no categories match.
    """
    if pd.isna(desc):
        return None
    
    desc_lower = str(desc).lower()
    
    # 1. Elevators
    if any(k in desc_lower for k in ["elevator", "lift", "elev"]):
        return "Elevators"
        
    # 2. Hot Water
    if any(k in desc_lower for k in ["hot water", "boiler", "hw", "h.w."]):
        return "Hot Water"
        
    # 3. Heat
    if any(k in desc_lower for k in ["heat", "heating", "radiator"]) or ("cold" in desc_lower and "water" not in desc_lower):
        return "Heat"
        
    # 4. Leaks
    if any(k in desc_lower for k in ["sink", "toilet", "leak", "leaking", "flood", "drip", "dripping", "pipe", "plumbing", "clog", "overflow", "faucet", "sewer", "drain", "water"]):
        return "Leaks"
        
    # 5. Roof
    if any(k in desc_lower for k in ["roof", "roofing", "gutter", "shingle", "ceiling"]):
        return "Roof"
        
    return None


def get_season(date) -> str | None:
    """
    Get the meteorological season for a given date.
    - Winter: Dec, Jan, Feb
    - Spring: Mar, Apr, May
    - Summer: Jun, Jul, Aug
    - Fall: Sep, Oct, Nov
    """
    if pd.isna(date):
        return None
    month = date.month
    if month in [12, 1, 2]:
        return "Winter"
    elif month in [3, 4, 5]:
        return "Spring"
    elif month in [6, 7, 8]:
        return "Summer"
    else:
        return "Fall"
