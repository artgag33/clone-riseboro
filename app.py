import streamlit as st

st.set_page_config(
    page_title="Riseboro Predictive Analytics",
    page_icon=":rocket:",
    layout="wide",
)

from src.auth import require_login

require_login()

pg = st.navigation(
    [
        st.Page(
            "pages/home.py",
            title="Operations Dashboard",
            icon=":material/dashboard:",
            default=True,
        ),
        st.Page(
            "pages/financials.py",
            title="Financials Dashboard",
            icon=":material/payments:",
        ),
        st.Page(
            "pages/upload.py",
            title="Upload Work Orders",
            icon=":material/upload_file:",
        ),
    ]
)
pg.run()

with st.sidebar:
    st.markdown(
        ":material/code: [Hoyalytics](https://hoyalytics.org)"
    )
