"""
JAL-RAKSHAK: Simple Login Module
Adds a username/password gate in front of the Streamlit dashboard.

Default credentials (for demo/hackathon use):
    username: admin       password: jalrakshak2026
    username: asha        password: asha2026

To use your own credentials instead of the defaults, set an environment
variable on Render (or Streamlit secrets) named JAL_RAKSHAK_USERS as a
JSON string, e.g.:

    JAL_RAKSHAK_USERS = {"admin": "yourpassword", "asha_majuli": "anotherpass"}

Passwords are compared as plain text here for simplicity (hackathon/demo
scope) — for a real production deployment, store hashed passwords instead.
"""

import streamlit as st
import os
import json

DEFAULT_USERS = {
    "admin": "jalrakshak2026",
    "asha": "asha2026",
}


def _load_users():
    raw = os.environ.get("JAL_RAKSHAK_USERS")
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    return DEFAULT_USERS


def require_login():
    """
    Call this at the top of app.py, right after st.set_page_config().
    Shows a login form and stops execution until the user logs in.
    Once logged in, sets st.session_state.logged_in = True and
    st.session_state.username to the logged-in user.
    """
    if st.session_state.get("logged_in"):
        return  # already logged in, let the app continue

    users = _load_users()

    st.markdown(
        """
        <div style="max-width:420px;margin:4rem auto 0 auto;padding:2rem;
        background:linear-gradient(135deg,#0b5394,#1c7ed6);border-radius:14px;">
        <h1 style="color:white;margin:0 0 4px 0;font-size:26px;">💧 JAL-RAKSHAK</h1>
        <p style="color:#dbeeff;margin:0;font-size:14px;">Early Warning Dashboard — Login</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        col = st.columns([1, 2, 1])[1]
        with col:
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in", use_container_width=True)

    if submitted:
        if username in users and password == users[username]:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.rerun()
        else:
            st.error("Invalid username or password.")

    st.stop()  # prevents the rest of app.py from running until login succeeds


def logout_button():
    """Call this in the sidebar to show a logout button."""
    if st.session_state.get("logged_in"):
        st.sidebar.markdown(f"👤 Logged in as **{st.session_state.get('username')}**")
        if st.sidebar.button("Log out"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.rerun()
