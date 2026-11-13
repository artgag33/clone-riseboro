"""
categorize.py — work-order classification engine.

Descriptions are free text typed by staff over ~17 years, so classification is
done with ordered regex anchors rather than exact matching: the first pattern
that hits wins, and patterns are ordered most-specific-first. The patterns
themselves live in anchors.py; this module is the engine that applies them.

Everything here is pure — no printing, no file I/O, no module-level execution.
Importing this module does nothing observable, which is what makes it safe to
call from a Streamlit app, a notebook, or a test.
"""

from __future__ import annotations

import pandas as pd

from anchors import ADDRESS_ONLY_RE, SUBCATEGORY_ANCHORS, TIER1_ANCHORS

# Near-duplicate category strings that mean the same thing in Yardi.
CATEGORY_CANONICAL = {
    "Inspections": "Inspection",
    "Exterminating": "Extermination",
}

# Two naming conventions exist for the same three columns. The source-of-truth
# workbook and the analysis modules use the right-hand names, so normalize onto
# those on the way in.
CANONICAL_COLUMNS = {
    "category_final": "final_category",
    "subcat_primary": "subcategory_primary",
    "subcat_secondary": "subcategory_secondary",
}

# Values of the subcat_source column, recording how each label was derived.
SOURCE_CATEGORY_ANCHOR = "category_anchor"  # matched its own category's anchors
SOURCE_TOPIC_FALLBACK = "topic_fallback"  # labeled by topic; likely mis-filed
SOURCE_ADDRESS_ONLY = "address_only"  # description is just an address
SOURCE_BLANK_DESC = "blank_desc"  # no description at all
SOURCE_UNMATCHED = "unmatched"  # nothing matched

# Placeholder labels that classify() returns instead of a real subcategory.
_NON_SUBCATEGORY_LABELS = {
    "Other": SOURCE_UNMATCHED,
    "Blank/No Desc": SOURCE_BLANK_DESC,
    "Address-Only (No Work Desc)": SOURCE_ADDRESS_ONLY,
}


def canonicalize_categories(df: pd.DataFrame, column: str = "category") -> pd.DataFrame:
    """Collapse near-duplicate category labels. Returns a copy."""
    df = df.copy()
    df[column] = df[column].replace(CATEGORY_CANONICAL)
    return df


def classify(desc, anchors) -> tuple[str, str]:
    """
    Return (subcat_primary, subcat_secondary) for one description.

    The first anchor to match becomes the primary label; any further matches are
    joined into the secondary field, which is useful for descriptions covering
    more than one issue ("Bathroom leak/Kitchen faucet").
    """
    if pd.isna(desc) or str(desc).strip() == "":
        return "Blank/No Desc", ""
    norm = str(desc).strip().lower()
    matched = []
    for label, pattern in anchors:
        if pattern.search(norm) and label not in matched:
            matched.append(label)
    if matched:
        return matched[0], "; ".join(matched[1:])
    if ADDRESS_ONLY_RE.match(norm):
        return "Address-Only (No Work Desc)", ""
    return "Other", ""


def infer_tier1(desc) -> str:
    """Infer a tier-1 category for a row whose category field is blank."""
    if pd.isna(desc) or str(desc).strip() == "":
        return "Blank/No Desc"
    norm = str(desc).strip().lower()
    for label, pattern in TIER1_ANCHORS:
        if pattern.search(norm):
            return label
    if ADDRESS_ONLY_RE.match(norm):
        return "Address-Only"
    return "Uncategorized"


def subcategory_table(
    df: pd.DataFrame, column: str = "subcategory_primary"
) -> pd.DataFrame:
    """Count and percentage breakdown of subcategories, most frequent first."""
    table = df[column].value_counts(dropna=False).reset_index()
    table.columns = [column, "count"]
    table["pct_of_category"] = (table["count"] / len(df) * 100).round(1)
    return table


# ---------------------------------------------------------------------------
# Topic fallback
# ---------------------------------------------------------------------------


def detect_topic(desc) -> str | None:
    """
    Identify what a description is *about*, ignoring the category it was filed under.

    Some Yardi categories hold descriptions that name the object rather than the
    work — an Inspection row reading "lights", a Carpentry row reading "soap
    dish". No amount of category-specific anchoring will label those, but the
    tier-1 anchors recognize them immediately. Returns None when nothing matches.
    """
    if pd.isna(desc) or str(desc).strip() == "":
        return None
    norm = str(desc).strip().lower()
    for label, pattern in TIER1_ANCHORS:
        if pattern.search(norm):
            return label
    return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def enrich_work_orders(
    df: pd.DataFrame, *, topic_fallback: bool = True
) -> pd.DataFrame:
    """
    Categorize and subcategorize a work-order dataset.

    Accepts either column-naming convention and returns a copy carrying
    final_category, subcategory_primary, subcategory_secondary, and
    subcat_source. Subcategories are recomputed from the anchors rather than
    preserved, so the result reflects the current patterns and re-running is
    idempotent.

    With topic_fallback enabled, rows whose description matches none of their
    own category's anchors are labeled by topic instead of "Other" — and
    subcat_source marks them, so `df[df.subcat_source == "topic_fallback"]`
    lists the rows that look mis-filed in Yardi.
    """
    df = df.rename(columns=CANONICAL_COLUMNS).copy()

    # Fill any missing category from the description before subcategorizing.
    if "final_category" not in df.columns:
        df["final_category"] = pd.NA
    missing = df["final_category"].isna()
    if missing.any():
        df.loc[missing, "final_category"] = df.loc[missing, "brief_desc"].apply(
            infer_tier1
        )

    primary = pd.Series(pd.NA, index=df.index, dtype=object)
    secondary = pd.Series(pd.NA, index=df.index, dtype=object)
    source = pd.Series(pd.NA, index=df.index, dtype=object)

    # Classify each category's rows against its own anchors. Partitioning means
    # every row is visited exactly once regardless of how many anchor sets exist.
    for category, anchors in SUBCATEGORY_ANCHORS.items():
        mask = df["final_category"] == category
        if not mask.any():
            continue
        results = [classify(desc, anchors) for desc in df.loc[mask, "brief_desc"]]
        primary.loc[mask] = [r[0] for r in results]
        secondary.loc[mask] = [r[1] for r in results]
        source.loc[mask] = [
            _NON_SUBCATEGORY_LABELS.get(r[0], SOURCE_CATEGORY_ANCHOR) for r in results
        ]

    # Rows in categories with no anchors of their own get no primary label yet.
    unanchored = source.isna()
    if unanchored.any():
        source.loc[unanchored] = [
            (
                SOURCE_BLANK_DESC
                if pd.isna(d) or str(d).strip() == ""
                else SOURCE_UNMATCHED
            )
            for d in df.loc[unanchored, "brief_desc"]
        ]
        primary.loc[unanchored] = [
            "Blank/No Desc" if pd.isna(d) or str(d).strip() == "" else "Other"
            for d in df.loc[unanchored, "brief_desc"]
        ]
        secondary.loc[unanchored] = ""

    if topic_fallback:
        # Only rows that genuinely matched nothing are eligible — never overwrite
        # a real anchor hit, and leave blank/address-only rows labeled as such.
        eligible = source == SOURCE_UNMATCHED
        if eligible.any():
            topics = [detect_topic(d) for d in df.loc[eligible, "brief_desc"]]
            idx = df.index[eligible]
            own_categories = df.loc[eligible, "final_category"]
            for row_idx, topic, own_category in zip(
                idx, topics, own_categories, strict=True
            ):
                # A topic identical to the row's own category is not new
                # information ("Plumbing" filed under Plumbing, restated) — it
                # only means the description matched a TIER1 keyword without
                # matching any of that category's own subcategory anchors.
                # Leaving it "Other" is more honest than a tautological label.
                if topic is not None and topic != own_category:
                    primary.at[row_idx] = topic
                    source.at[row_idx] = SOURCE_TOPIC_FALLBACK

    df["subcategory_primary"] = primary
    df["subcategory_secondary"] = secondary
    df["subcat_source"] = source
    return df


def coverage_report(df: pd.DataFrame) -> pd.DataFrame:
    """
    Per-category classification quality, worst first — the anchor tuning dashboard.

    Columns: row count, and the share of rows landing in each subcat_source
    bucket. A high `unmatched_pct` means that category needs more anchors.
    """
    rows = []
    for category, group in df.groupby("final_category", dropna=False):
        n = len(group)
        counts = group["subcat_source"].value_counts()
        rows.append(
            {
                "category": category,
                "n": n,
                "anchored_pct": round(
                    counts.get(SOURCE_CATEGORY_ANCHOR, 0) / n * 100, 1
                ),
                "fallback_pct": round(
                    counts.get(SOURCE_TOPIC_FALLBACK, 0) / n * 100, 1
                ),
                "unmatched_pct": round(counts.get(SOURCE_UNMATCHED, 0) / n * 100, 1),
                "blank_pct": round(counts.get(SOURCE_BLANK_DESC, 0) / n * 100, 1),
                "has_anchors": category in SUBCATEGORY_ANCHORS,
            }
        )
    return (
        pd.DataFrame(rows)
        .sort_values(["unmatched_pct", "n"], ascending=[False, False])
        .reset_index(drop=True)
    )


def unmatched_descriptions(df: pd.DataFrame, category: str) -> pd.Series:
    """Distinct descriptions in one category that matched nothing — raw material for new anchors."""
    mask = (df["final_category"] == category) & (
        df["subcat_source"] == SOURCE_UNMATCHED
    )
    return df.loc[mask, "brief_desc"].dropna().value_counts()
