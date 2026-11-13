"""
hpd_charges.py — client for NYC HPD Fee Charges dataset (NYC Open Data / Socrata).

Dataset ID: cp6j-7bjj
Covers fees assessed against properties by the NYC Department of Housing
Preservation and Development (HPD) pursuant to the Housing Maintenance Code.

Supports searching by:
  - Street address (e.g. "1245 Gates Ave", "1245 Gates Avenue, Brooklyn")
  - Building components (house number, street name, borough)
  - BIN (Building Identification Number)
  - BBL (Borough-Block-Lot)
  - HPD Building ID

Reads SOCRATA_TOKEN from .env or environment for authenticated, higher-rate requests.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pandas as pd
import requests

SOCRATA_BASE = "https://data.cityofnewyork.us/resource"
DATASET_ID = "cp6j-7bjj"

# Socrata's firewall rejects requests without a browser-like user agent.
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

# Socrata caps a single response at 50,000 rows.
MAX_PAGE_SIZE = 50_000

# Standard NYC street abbreviation expansions to match HPD dataset conventions
STREET_ABBREVIATIONS: dict[str, str] = {
    "AVE": "AVENUE",
    "AV": "AVENUE",
    "ST": "STREET",
    "STR": "STREET",
    "RD": "ROAD",
    "PL": "PLACE",
    "BLVD": "BOULEVARD",
    "PKWY": "PARKWAY",
    "PWKY": "PARKWAY",
    "DR": "DRIVE",
    "CT": "COURT",
    "LN": "LANE",
    "TER": "TERRACE",
    "TERR": "TERRACE",
    "HWY": "HIGHWAY",
    "EXPY": "EXPRESSWAY",
    "EXP": "EXPRESSWAY",
    "TPKE": "TURNPIKE",
    "WAY": "WAY",
    "E": "EAST",
    "W": "WEST",
    "N": "NORTH",
    "S": "SOUTH",
}

# Mapping of borough aliases/names to official HPD borough names
BOROUGH_MAP: dict[str, str] = {
    "MANHATTAN": "MANHATTAN",
    "NEW YORK": "MANHATTAN",
    "MN": "MANHATTAN",
    "BRONX": "BRONX",
    "THE BRONX": "BRONX",
    "BX": "BRONX",
    "BROOKLYN": "BROOKLYN",
    "BKLYN": "BROOKLYN",
    "BK": "BROOKLYN",
    "KINGS": "BROOKLYN",
    "QUEENS": "QUEENS",
    "QNS": "QUEENS",
    "QN": "QUEENS",
    "STATEN ISLAND": "STATEN ISLAND",
    "SI": "STATEN ISLAND",
    "RICHMOND": "STATEN ISLAND",
}

# Mapping of numeric borough IDs (e.g. 1-5) if supplied directly
BORO_ID_MAP: dict[str, str] = {
    "1": "MANHATTAN",
    "2": "BRONX",
    "3": "BROOKLYN",
    "4": "QUEENS",
    "5": "STATEN ISLAND",
}


def _find_env_file() -> Path | None:
    """Locate the .env file in the current directory or parent tree."""
    curr = Path.cwd().resolve()
    for parent in [curr, *curr.parents]:
        env_file = parent / ".env"
        if env_file.is_file():
            return env_file
    this_dir = Path(__file__).resolve().parent
    for parent in [this_dir, *this_dir.parents]:
        env_file = parent / ".env"
        if env_file.is_file():
            return env_file
    return None


def get_socrata_token() -> str | None:
    """
    Retrieve the SOCRATA_TOKEN from environment variables, .env file, or Streamlit secrets.
    """
    # 1. Direct environment variable
    token = os.environ.get("SOCRATA_TOKEN") or os.environ.get("APP_TOKEN")
    if token and token.strip():
        return token.strip()

    # 2. Check .env file directly if not in os.environ
    env_path = _find_env_file()
    if env_path and env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, _, val = line.partition("=")
                        key = key.strip().removeprefix("export ").strip()
                        val = val.strip().strip("\"'")
                        if key in ("SOCRATA_TOKEN", "APP_TOKEN") and val:
                            os.environ[key] = val
                            return val
        except Exception:
            pass

    # 3. Streamlit secrets fallback
    try:
        import streamlit as st

        if hasattr(st, "secrets"):
            if "SOCRATA_TOKEN" in st.secrets:
                return str(st.secrets["SOCRATA_TOKEN"]).strip()
            if "socrata" in st.secrets and "token" in st.secrets["socrata"]:
                return str(st.secrets["socrata"]["token"]).strip()
    except Exception:
        pass

    return None


def _get_request_headers() -> dict[str, str]:
    """Build request headers, injecting Socrata App Token if available."""
    headers = dict(DEFAULT_HEADERS)
    token = get_socrata_token()
    if token:
        headers["X-App-Token"] = token
    return headers


def normalize_street_name(street: str) -> str:
    """
    Normalize street name to match HPD convention:
    - Strips punctuation and extra whitespace
    - Converts to uppercase
    - Expands common abbreviations (AVE -> AVENUE, ST -> STREET, etc.)
    """
    s = re.sub(r"[^\w\s]", " ", street).strip().upper()
    tokens = s.split()
    normalized_tokens = [STREET_ABBREVIATIONS.get(t, t) for t in tokens]
    return " ".join(normalized_tokens)


def parse_address(address: str) -> tuple[str | None, str, str | None]:
    """
    Parse a raw address string into (house_number, street_name, borough).

    Examples:
      - "1245 Gates Ave, Brooklyn, NY 11221" -> ("1245", "GATES AVENUE", "BROOKLYN")
      - "100 Broadway, Manhattan, NY" -> ("100", "BROADWAY", "MANHATTAN")
      - "50-10 43rd Ave, Queens" -> ("50-10", "43RD AVENUE", "QUEENS")
      - "1245 Gates Avenue" -> ("1245", "GATES AVENUE", None)
    """
    s = address.strip()

    # Strip trailing NY and zip code (e.g., ", NY 11221" or "NY 10001" or "11221")
    s = re.sub(r",?\s*(?:NY|NEW\s+YORK)?\s*\b\d{5}(?:-\d{4})?\b\s*$", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r",?\s*\bNY\b\s*$", "", s, flags=re.IGNORECASE).strip()

    # Detect borough from trailing section or comma-separated components
    detected_borough: str | None = None
    # Sort borough keys by length descending to match multi-word names first
    sorted_boros = sorted(BOROUGH_MAP.keys(), key=len, reverse=True)
    for b_key in sorted_boros:
        # Check if borough occurs at the end of the address or after a comma
        pattern = rf"(?:,\s*|\s+)\b{re.escape(b_key)}\b\s*$"
        match = re.search(pattern, s, re.IGNORECASE)
        if match:
            detected_borough = BOROUGH_MAP[b_key]
            s = s[: match.start()].strip().rstrip(",")
            break

    # Extract house number (handles hyphenated NYC house numbers like "50-10" or regular numbers "1245")
    house_match = re.match(r"^(\d+(?:-\d+)?(?:[A-Za-z])?)\s+(.*)$", s)
    if house_match:
        house_number = house_match.group(1).strip()
        raw_street = house_match.group(2).strip()
        street_name = normalize_street_name(raw_street)
        return house_number, street_name, detected_borough

    return None, normalize_street_name(s), detected_borough


def fetch(
    dataset: str = DATASET_ID,
    *,
    limit: int = 1000,
    offset: int = 0,
    timeout: int = 30,
    **filters: Any,
) -> pd.DataFrame:
    """
    Fetch rows from the Socrata dataset as a DataFrame.

    dataset defaults to 'cp6j-7bjj' (HPD Fee Charges).
    Extra keyword arguments become SoQL parameters:
      - `where="housenumber='1245'"`
      - `select="feeid, housenumber, streetname, feeamount"`
      - `order="feeissueddate DESC"`
      - `q="1245 Gates"`
      - Equality filters like `boro="BROOKLYN"` or `feetype="Emergency Repair"`
    """
    params: dict[str, Any] = {"$limit": limit, "$offset": offset}
    token = get_socrata_token()
    if token:
        params["$$app_token"] = token

    for key, value in filters.items():
        if value is not None:
            param_key = f"${key}" if key in {"where", "select", "order", "q", "group", "having"} else key
            params[param_key] = value

    headers = _get_request_headers()
    response = requests.get(
        f"{SOCRATA_BASE}/{dataset}.json",
        headers=headers,
        params=params,
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    return df


def fetch_all(
    dataset: str = DATASET_ID,
    *,
    page_size: int = MAX_PAGE_SIZE,
    max_rows: int | None = None,
    timeout: int = 30,
    **filters: Any,
) -> pd.DataFrame:
    """
    Page through a dataset until exhausted or max_rows is reached.
    """
    frames: list[pd.DataFrame] = []
    offset = 0

    while True:
        limit = page_size
        if max_rows is not None:
            remaining = max_rows - offset
            if remaining <= 0:
                break
            limit = min(page_size, remaining)

        page = fetch(dataset, limit=limit, offset=offset, timeout=timeout, **filters)
        if page.empty:
            break

        frames.append(page)
        offset += len(page)
        if len(page) < limit or (max_rows is not None and offset >= max_rows):
            break

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    return combined.head(max_rows) if max_rows is not None else combined


def search_by_address(
    address: str,
    *,
    borough: str | None = None,
    exact_street: bool = False,
    limit: int = 1000,
    max_rows: int | None = None,
    timeout: int = 30,
    **extra_filters: Any,
) -> pd.DataFrame:
    """
    Search HPD Fee Charges by street address.

    Parameters:
      address: Raw address string (e.g. "1245 Gates Ave", "1245 Gates Avenue, Brooklyn, NY").
      borough: Optional borough name or code to filter by (e.g. 'BROOKLYN', '3', 'BK').
      exact_street: If True, requires exact match on normalized street name; otherwise uses prefix match.
      limit: Maximum number of rows to return per page.
      max_rows: Maximum total rows to return (None for all matching rows).
      timeout: Timeout in seconds for requests.
      **extra_filters: Additional SoQL/column filters (e.g. feeissueddate="...").

    Returns:
      DataFrame containing matching HPD fee charge records.
    """
    house_num, street_name, detected_boro = parse_address(address)
    final_boro = borough or detected_boro
    if final_boro:
        final_boro = BOROUGH_MAP.get(str(final_boro).upper().strip(), final_boro.upper().strip())

    where_clauses: list[str] = []

    if house_num:
        # Standardize house number comparison
        where_clauses.append(f"housenumber = '{house_num}'")

    if street_name:
        # Escape single quotes in street name
        safe_street = street_name.replace("'", "''")
        if exact_street:
            where_clauses.append(f"upper(streetname) = '{safe_street}'")
        else:
            # Match street prefix or exact
            where_clauses.append(f"upper(streetname) like '{safe_street}%'")

    if final_boro:
        safe_boro = final_boro.replace("'", "''")
        where_clauses.append(f"upper(boro) = '{safe_boro}'")

    # If extra where clause was provided, combine with AND
    if "where" in extra_filters:
        custom_where = extra_filters.pop("where")
        if custom_where:
            where_clauses.append(f"({custom_where})")

    combined_where = " AND ".join(where_clauses) if where_clauses else None

    # If no structured fields could be parsed, fallback to Socrata full-text search $q
    filters = dict(extra_filters)
    if combined_where:
        filters["where"] = combined_where
    else:
        filters["q"] = address

    if max_rows is not None and max_rows > limit:
        return fetch_all(DATASET_ID, page_size=limit, max_rows=max_rows, timeout=timeout, **filters)
    return fetch(DATASET_ID, limit=limit, timeout=timeout, **filters)


def search_by_building(
    house_number: str | int,
    street_name: str,
    *,
    borough: str | None = None,
    exact_street: bool = False,
    limit: int = 1000,
    max_rows: int | None = None,
    timeout: int = 30,
    **extra_filters: Any,
) -> pd.DataFrame:
    """
    Search HPD Fee Charges by explicit house number, street name, and optional borough.
    """
    normalized_street = normalize_street_name(str(street_name))
    query_address = f"{house_number} {normalized_street}"
    return search_by_address(
        query_address,
        borough=borough,
        exact_street=exact_street,
        limit=limit,
        max_rows=max_rows,
        timeout=timeout,
        **extra_filters,
    )


def search_by_bin(
    bin_number: str | int,
    *,
    limit: int = 1000,
    max_rows: int | None = None,
    timeout: int = 30,
    **extra_filters: Any,
) -> pd.DataFrame:
    """
    Search HPD Fee Charges by Building Identification Number (BIN).
    """
    filters = dict(extra_filters)
    where_clauses = [f"bin = '{bin_number}'"]
    if "where" in filters:
        custom_where = filters.pop("where")
        if custom_where:
            where_clauses.append(f"({custom_where})")
    filters["where"] = " AND ".join(where_clauses)

    if max_rows is not None and max_rows > limit:
        return fetch_all(DATASET_ID, page_size=limit, max_rows=max_rows, timeout=timeout, **filters)
    return fetch(DATASET_ID, limit=limit, timeout=timeout, **filters)


def search_by_bbl(
    bbl: str | int,
    *,
    limit: int = 1000,
    max_rows: int | None = None,
    timeout: int = 30,
    **extra_filters: Any,
) -> pd.DataFrame:
    """
    Search HPD Fee Charges by Borough-Block-Lot (BBL).
    """
    filters = dict(extra_filters)
    where_clauses = [f"bbl = '{bbl}'"]
    if "where" in filters:
        custom_where = filters.pop("where")
        if custom_where:
            where_clauses.append(f"({custom_where})")
    filters["where"] = " AND ".join(where_clauses)

    if max_rows is not None and max_rows > limit:
        return fetch_all(DATASET_ID, page_size=limit, max_rows=max_rows, timeout=timeout, **filters)
    return fetch(DATASET_ID, limit=limit, timeout=timeout, **filters)


def search_by_building_id(
    building_id: str | int,
    *,
    limit: int = 1000,
    max_rows: int | None = None,
    timeout: int = 30,
    **extra_filters: Any,
) -> pd.DataFrame:
    """
    Search HPD Fee Charges by HPD Building ID.
    """
    filters = dict(extra_filters)
    where_clauses = [f"buildingid = '{building_id}'"]
    if "where" in filters:
        custom_where = filters.pop("where")
        if custom_where:
            where_clauses.append(f"({custom_where})")
    filters["where"] = " AND ".join(where_clauses)

    if max_rows is not None and max_rows > limit:
        return fetch_all(DATASET_ID, page_size=limit, max_rows=max_rows, timeout=timeout, **filters)
    return fetch(DATASET_ID, limit=limit, timeout=timeout, **filters)
