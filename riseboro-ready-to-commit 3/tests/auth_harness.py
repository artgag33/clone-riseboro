import streamlit as st
st.set_page_config(page_title='Riseboro login test')
from src.auth import require_login
require_login()
st.title('Protected dashboard test')
st.session_state.setdefault('wo_df', 'test uploaded data')
st.button('Refresh dashboard')
