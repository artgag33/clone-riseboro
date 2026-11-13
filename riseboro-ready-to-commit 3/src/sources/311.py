"""
nyc_open_data.py — client for NYC Open Data (Socrata) datasets.

Covers the 311 complaints feed used for address matching against the portfolio.
Generalized from riseboro_rows.py, which fetched a fixed 10 rows to inspect the
schema.
"""

from __future__ import annotations

import pandas as pd
import requests

SOCRATA_BASE = "https://data.cityofnewyork.us/resource"

DATASETS = {
    "311": "erm2-nwe9",
}

# Socrata's firewall rejects requests without a browser-like user agent.
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

# Socrata caps a single response at 50,000 rows.
MAX_PAGE_SIZE = 50_000


def fetch(
    dataset: str,
    *,
    limit: int = 1000,
    offset: int = 0,
    timeout: int = 30,
    **filters,
) -> pd.DataFrame:
    """
    Fetch rows from a Socrata dataset as a DataFrame.

    dataset is a key from DATASETS or a raw resource id. Extra keyword arguments
    become SoQL parameters, so `fetch("311", where="borough='BROOKLYN'")` and
    equality filters like `complaint_type="HEAT/HOT WATER"` both work.
    """
    resource = DATASETS.get(dataset, dataset)
    params = {"$limit": limit, "$offset": offset}
    for key, value in filters.items():
        params[f"${key}" if key in {"where", "select", "order", "q"} else key] = value

    response = requests.get(
        f"{SOCRATA_BASE}/{resource}.json",
        headers=DEFAULT_HEADERS,
        params=params,
        timeout=timeout,
    )
    response.raise_for_status()
    return pd.DataFrame(response.json())


def fetch_all(
    dataset: str,
    *,
    page_size: int = MAX_PAGE_SIZE,
    max_rows: int | None = None,
    **filters,
) -> pd.DataFrame:
    """
    Page through a dataset until exhausted or max_rows is reached.

    The 311 dataset holds tens of millions of rows — always pass filters or
    max_rows rather than calling this bare.
    """
    frames, offset = [], 0
    while True:
        page = fetch(dataset, limit=page_size, offset=offset, **filters)
        if page.empty:
            break
        frames.append(page)
        offset += len(page)
        if len(page) < page_size or (max_rows is not None and offset >= max_rows):
            break

    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    return combined.head(max_rows) if max_rows is not None else combined
