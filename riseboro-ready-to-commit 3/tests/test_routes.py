from pathlib import Path
import hashlib
import json
import bcrypt
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from streamlit.runtime.pages_manager import PagesManager

ROOT = Path(__file__).resolve().parents[1]
PAGES = ['home', 'financials', 'upload']

@pytest.fixture
def config():
    return {'credentials': {'usernames': {'tester': {'name':'Test User', 'password':bcrypt.hashpw(b'local-test-only',bcrypt.gensalt(rounds=4)).decode()}}},'cookie': {'name':'test_routes','key':'test-only-key-1234567890123456789012345','expiry_days':1}}

def app(config, file='app.py'):
    at=AppTest.from_file(str(ROOT/file), default_timeout=30)
    at.secrets['auth']=config
    return at

def sign_in(at):
    at.text_input[0].set_value('tester')
    at.text_input[1].set_value('local-test-only')
    at.button(key='FormSubmitter:riseboro_login-Login').click().run()
    assert not at.exception
    assert at.session_state['authentication_status'] is True
    return at

def assert_locked(at):
    assert not at.exception
    assert not at.get('file_uploader')
    assert not at.get('dataframe')
    assert not at.multiselect
    assert not at.metric
    assert not at.get('plotly_chart')
    assert not at.get('deck_gl_json_chart')
    assert len(at.text_input)==2 or bool(at.error)

@pytest.mark.parametrize('page',PAGES)
def test_cold_deep_link_requires_login_before_data(config,page,monkeypatch):
    def forbidden(*args,**kwargs):
        raise AssertionError('Unauthenticated page attempted to read data')
    monkeypatch.setattr(pd,'read_csv',forbidden)
    PagesManager.uses_pages_directory=None
    at=app(config)
    at.switch_page(f'dashboard_pages/{page}.py').run()
    assert_locked(at)
    assert len(at.text_input)==2
    assert not PagesManager.uses_pages_directory

@pytest.mark.parametrize('page',PAGES)
def test_page_script_itself_fails_closed(config,page,monkeypatch):
    monkeypatch.setattr(pd,'read_csv',lambda *a,**k: pytest.fail('Read before auth'))
    at=app(config,f'dashboard_pages/{page}.py').run()
    assert_locked(at)
    assert 'Please sign in' in at.error[0].value

@pytest.mark.parametrize('page',PAGES)
def test_false_or_stale_session_cannot_open_page(config,page):
    at=app(config,f'dashboard_pages/{page}.py')
    at.session_state['authentication_status']=True
    at.session_state['username']='tester'
    at.session_state['_auth_config_fingerprint']='stale'
    at.session_state['wo_df']='private uploaded data'
    at.run()
    assert_locked(at)
    assert 'wo_df' not in at.session_state

@pytest.mark.parametrize('page',PAGES)
def test_logout_blocks_every_route(config,page,monkeypatch):
    import src.financials as financials
    monkeypatch.setattr(financials,'load_portfolio_hpd_charges',lambda *_:pd.DataFrame())
    at=sign_in(app(config).run())
    at.switch_page(f'dashboard_pages/{page}.py').run()
    assert not at.exception
    assert not any(field.label in ('Username', 'Password') for field in at.text_input)
    at.session_state['wo_df']=pd.DataFrame({'private':['test']})
    at.button(key='riseboro_logout').click().run()
    assert_locked(at)
    assert 'wo_df' not in at.session_state
    at.switch_page(f'dashboard_pages/{page}.py').run()
    assert_locked(at)


def test_separate_browser_session_is_not_authenticated(config):
    first=sign_in(app(config).run())
    second=app(config).run()
    assert first.session_state['authentication_status'] is True
    assert second.session_state.get('authentication_status') is not True
    assert_locked(second)


def test_sidebar_names_and_icons_preserved(config):
    at=app(config).run()
    entries=at._registered_pages.values()
    assert [(p['page_name'],p['icon']) for p in entries] == [
        ('Operations Dashboard',':material/dashboard:'),
        ('Financials Dashboard',':material/payments:'),
        ('Upload Work Orders',':material/upload_file:')]


def test_no_auto_discovered_pages():
    assert not list((ROOT/'pages').glob('*.py'))

@pytest.mark.parametrize('kind',['expired','invalid_signature'])
def test_invalid_cookie_does_not_authenticate(config,kind,monkeypatch):
    import time
    import jwt
    import streamlit as st
    from types import SimpleNamespace
    key=config['cookie']['key'] if kind=='expired' else 'different-test-signing-key-1234567890'
    token=jwt.encode({'username':'tester','exp_date':time.time()+(-60 if kind=='expired' else 3600)},key,algorithm='HS256')
    monkeypatch.setattr(st,'context',SimpleNamespace(cookies={'test_routes':token}))
    at=app(config).run()
    assert_locked(at)
    assert at.session_state['authentication_status'] is not True
