"""Shared login gate. Call before navigation or imports that read private data."""
import os
import hashlib
import json
from pathlib import Path

import streamlit as st
import streamlit_authenticator as stauth
import yaml
from streamlit.errors import StreamlitSecretNotFoundError

from src.auth_config import AuthConfigurationError, validate_config


def load_config():
    # Cloud secrets use TOML, with the same credentials/cookie structure as YAML.
    try:
        if 'auth' in st.secrets:
            return validate_config(st.secrets['auth'].to_dict())
    except StreamlitSecretNotFoundError:
        pass
    path = Path(os.environ.get('RISEBORO_AUTH_CONFIG', 'credentials.yaml'))
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    with path.open(encoding='utf-8') as file:
        return validate_config(yaml.safe_load(file))


def clear_dashboard_session(_event=None):
    # Logout must not leave uploaded work orders for the next account in this tab.
    # The library restores its own authentication defaults on the next rerun.
    for key in list(st.session_state):
        del st.session_state[key]


def require_login():
    try:
        config = load_config()
    except (OSError, ValueError, TypeError, AttributeError, yaml.YAMLError):
        st.error('Dashboard sign-in is not configured. Please contact the dashboard administrator.')
        st.stop()

    # Keep attempt counters across reruns, isolated per browser session. A config
    # change clears active state so removed users cannot keep an open session.
    fingerprint = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    previous = st.session_state.get('_auth_config_fingerprint')
    if previous is not None and previous != fingerprint:
        clear_dashboard_session()
    if '_auth_credentials' not in st.session_state:
        st.session_state['_auth_credentials'] = config['credentials']
    st.session_state['_auth_config_fingerprint'] = fingerprint

    try:
        authenticator = stauth.Authenticate(
            credentials=st.session_state['_auth_credentials'],
            cookie_name=config['cookie']['name'],
            cookie_key=config['cookie']['key'],
            cookie_expiry_days=config['cookie']['expiry_days'],
            auto_hash=False,
        )
        authenticator.login(location='main', max_login_attempts=5,
                            clear_on_submit=True, key='riseboro_login')
    except Exception:
        # Do not show raw exceptions: they may include private auth configuration.
        st.error('Unable to sign in. Please try again or contact the dashboard administrator.')
        st.stop()

    status = st.session_state.get('authentication_status')
    username = st.session_state.get('username')
    if status is not True or username not in config['credentials']['usernames']:
        if status is False:
            st.error('Incorrect username or password.')
        else:
            st.info('Sign in to access the Riseboro dashboards.')
        st.stop()

    st.sidebar.caption(f"Signed in as {config['credentials']['usernames'][username]['name']}")
    authenticator.logout('Sign out', location='sidebar', key='riseboro_logout',
                         callback=clear_dashboard_session)
    # Logout can execute in this run; never continue into page code afterward.
    if st.session_state.get('authentication_status') is not True:
        st.rerun()
    return username
