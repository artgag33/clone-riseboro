from pathlib import Path
import bcrypt
import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parent / 'auth_harness.py'

@pytest.fixture
def app():
    at = AppTest.from_file(str(APP), default_timeout=15)
    at.secrets['auth'] = {
        'credentials': {'usernames': {'tester': {
            'name': 'Test User',
            'password': bcrypt.hashpw(b'local-test-only', bcrypt.gensalt(rounds=4)).decode(),
        }}},
        'cookie': {'name': 'test_auth', 'key': 'test-only-key-1234567890123456789012345', 'expiry_days': 1},
    }
    return at.run()

def login(at, password='local-test-only'):
    at.text_input[0].set_value('tester')
    at.text_input[1].set_value(password)
    return at.button[0].click().run()

def protected(at):
    return any(t.value == 'Protected dashboard test' for t in at.title)

def test_initial_gate(app):
    assert not app.exception
    assert len(app.text_input) == 2
    assert not protected(app)

def test_bad_password_stays_blocked(app):
    login(app, 'wrong')
    assert not app.exception
    assert not protected(app)
    assert app.error[0].value == 'Incorrect username or password.'

def test_login_clears_form_and_rerun_keeps_session(app):
    login(app)
    assert not app.exception
    assert protected(app)
    assert len(app.text_input) == 0
    app.run()
    assert not app.exception
    assert protected(app)
    assert len(app.text_input) == 0

def test_logout_clears_uploaded_data_and_blocks_pages(app):
    login(app)
    assert app.session_state['wo_df'] == 'test uploaded data'
    app.button(key='riseboro_logout').click().run()
    assert not app.exception
    assert not protected(app)
    assert len(app.text_input) == 2
    assert 'wo_df' not in app.session_state

def test_config_change_revokes_session(app):
    login(app)
    app.secrets['auth']['credentials']['usernames']['tester']['name'] = 'Changed'
    app.run()
    assert not app.exception
    assert not protected(app)
    assert 'wo_df' not in app.session_state

def test_invalid_config_fails_closed(app):
    app.secrets['auth']['cookie']['key'] = 'short'
    app.run()
    assert not app.exception
    assert not protected(app)
    assert 'not configured' in app.error[0].value
