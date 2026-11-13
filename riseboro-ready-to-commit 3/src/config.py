"""
config.py — single source of truth for paths, properties, and calendar labels.

Before this module existed, BASE_DIR boilerplate was copy-pasted into five
scripts, the path to the source-of-truth workbook into four, the property
registry into three, and the month-name map into three. Any change had to be
made in every copy. Import from here instead.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# PROJECT_ROOT is derived from this file's location: src/riseboro/config.py
# -> parents[0] = riseboro, parents[1] = src, parents[2] = repo root.
# That holds under an editable install, which is how this package is used.
# RISEBORO_DATA_DIR overrides it for containers or a non-editable install.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = Path(os.environ.get("RISEBORO_DATA_DIR", PROJECT_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
RAW_ARCHIVE_DIR = RAW_DIR / "archive"
PROCESSED_DIR = DATA_DIR / "processed"
CHARTS_DIR = PROCESSED_DIR / "charts"

SOURCE_OF_TRUTH = RAW_DIR / "WEEK 2 SOURCE OF TRUTH.xlsx"
ENRICHED_WORK_ORDERS = PROCESSED_DIR / "work_orders_enriched_final.xlsx"

# Raw Yardi exports consumed by scripts/build_dataset.py. These moved into
# raw/archive/ at some point, so resolve against whichever location has them.
WORK_ORDER_DIRECTORY_FILE = "WorkOrderDirectory06_01_2026.xlsx"
GATES_PLAZA_FILE = "Gates Plaza (1245 Gates Avenue).xlsx"
WEST_BUSHWICK_FILE = "wb203k.xlsx"


def yardi_export_dir() -> Path:
    """Directory holding the raw Yardi exports, falling back to raw/archive/."""
    if (RAW_DIR / WORK_ORDER_DIRECTORY_FILE).exists():
        return RAW_DIR
    return RAW_ARCHIVE_DIR


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Property:
    """A property under analysis, with its display name and chart color."""

    code: str
    name: str
    color: str


# Every property present in the work-order data. Reports iterate this dict, so
# adding an entry here puts a property into the trend, chart, and significance
# runs at once. test_config.py asserts this stays in sync with the data —
# west_bushwick_203k was missing for three weeks, which silently excluded 44%
# of the portfolio from every report.
PROPERTIES: dict[str, Property] = {
    "rheingold_gardens": Property(
        "rheingold_gardens", "Rheingold", "#4F46E5"
    ),  # indigo
    "gates_plaza": Property("gates_plaza", "Gates Plaza", "#0D9488"),  # teal
    "west_bushwick_203k": Property(
        "west_bushwick_203k", "West Bushwick 203K", "#B45309"
    ),  # amber
}


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

MONTH_NAMES: list[str] = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

MONTH_MAP: dict[int, str] = {i + 1: name for i, name in enumerate(MONTH_NAMES)}

# 2026 data is partial; charts and trend fits exclude it to avoid a false dip.
PARTIAL_YEAR = 2026
