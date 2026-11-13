"""
src/components.py
-----------------
Reusable UI helper components for the Riseboro dashboard.
"""

import streamlit as st


def metric_card(
    label: str,
    value: str,
    delta: str = "",
    delta_positive: bool = True,
    icon: str = "",
    show_arrow: bool = True,
):
    """Render a styled KPI metric card."""
    delta_color = "#22c55e" if delta_positive else "#ef4444"
    delta_arrow = ("▲ " if delta_positive else "▼ ") if show_arrow else ""
    delta_html = (
        f'<span style="color:{delta_color}; font-size:0.85rem; font-weight:600;">'
        f"{delta_arrow}{delta}</span>"
        if delta
        else ""
    )

    card_html = f"""
    <div style="
        background: linear-gradient(135deg, #013494 0%, #0252cc 100%);
        border-radius: 16px;
        padding: 1.4rem 1.6rem;
        color: white;
        box-shadow: 0 4px 20px rgba(1, 52, 148, 0.25);
        min-height: 130px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    ">
        <div style="font-size: 1.8rem; margin-bottom: 0.3rem;">{icon}</div>
        <div>
            <div style="font-size: 0.8rem; letter-spacing: 0.07em; text-transform: uppercase;
                        opacity: 0.75; margin-bottom: 0.25rem;">{label}</div>
            <div style="font-size: 2rem; font-weight: 700; line-height: 1;">{value}</div>
            <div style="margin-top: 0.4rem;">{delta_html}</div>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


def section_header(title: str, subtitle: str = ""):
    """Render a styled section header."""
    st.markdown(
        f"""
        <div style="margin: 1.5rem 0 0.75rem 0;">
            <h2 style="color:#013494; font-weight:700; margin:0; font-size:1.35rem;">
                {title}
            </h2>
            {"<p style='color:#64748b; margin:0.15rem 0 0 0; font-size:0.9rem;'>" + subtitle + "</p>" if subtitle else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )


def divider():
    """Styled horizontal divider."""
    st.markdown(
        "<hr style='border:none; border-top:1.5px solid #e2e8f0; margin: 0.5rem 0 1rem 0;'>",
        unsafe_allow_html=True,
    )
