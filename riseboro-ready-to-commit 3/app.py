import streamlit as st

st.set_page_config(
    page_title="Riseboro Predictive Analytics",
    page_icon=":rocket:",
    layout="wide",
)

pg = st.navigation(
    [
        st.Page(
            "dashboard_pages/home.py",
            title="Operations Dashboard",
            icon=":material/dashboard:",
            default=True,
        ),
        st.Page(
            "dashboard_pages/financials.py",
            title="Financials Dashboard",
            icon=":material/payments:",
        ),
        st.Page(
            "dashboard_pages/upload.py",
            title="Upload Work Orders",
            icon=":material/upload_file:",
        ),
    ]
)
# Register navigation before authentication can stop this run.
from src.auth import require_login

require_login()
pg.run()

with st.sidebar:
    st.markdown(
        ":material/code: [Hoyalytics](https://hoyalytics.org)"
    )
