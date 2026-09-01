"""Login and registration.

These credentials are for CampusSync AI only. We never ask for a university
password — external platforms will connect via OAuth or a revocable token.
"""

import streamlit as st

from frontend.api.backend_api import BackendError, backend_online, login, register


def _store_session(result: dict):
    st.session_state.token = result["token"]
    st.session_state.student_id = result["registration_no"]
    st.session_state.name = result.get("name", "")
    st.session_state.logged_in = True
    st.session_state.current_page = "dashboard"


def show_login():
    st.markdown(
        """
        <div class="main-title">🎓 CampusSync AI</div>
        <div class="subtitle">Your AI Academic Assistant</div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")

    if not backend_online():
        st.warning(
            "⚠️ Backend not reachable. Start it with `make backend` and make "
            "sure Ollama is running."
        )

    sign_in, sign_up = st.tabs(["Sign in", "Create account"])

    with sign_in:
        with st.form("login_form"):
            reg_no = st.text_input("Registration number", placeholder="24BAI1127")
            password = st.text_input("Password", type="password")

            if st.form_submit_button("Sign in", use_container_width=True):
                if not reg_no.strip() or not password:
                    st.warning("Please fill in both fields.")
                else:
                    try:
                        _store_session(login(reg_no.strip(), password))
                        st.rerun()
                    except BackendError as exc:
                        st.error(str(exc))

    with sign_up:
        with st.form("register_form"):
            new_reg = st.text_input(
                "Registration number", placeholder="24BAI1127", key="reg_no"
            )
            new_name = st.text_input("Name (optional)", key="reg_name")
            new_password = st.text_input(
                "Password", type="password", key="reg_pw"
            )
            confirm = st.text_input(
                "Confirm password", type="password", key="reg_pw2"
            )

            st.caption("Minimum 6 characters.")

            if st.form_submit_button("Create account", use_container_width=True):
                if not new_reg.strip():
                    st.warning("Registration number is required.")
                elif len(new_password) < 6:
                    st.warning("Password must be at least 6 characters.")
                elif new_password != confirm:
                    st.error("Passwords do not match.")
                else:
                    try:
                        _store_session(
                            register(
                                new_reg.strip(), new_password, new_name.strip()
                            )
                        )
                        st.rerun()
                    except BackendError as exc:
                        st.error(str(exc))

    st.divider()

    st.caption(
        "🔒 This password is for CampusSync AI only. We never ask for your "
        "university password — LMS and Google Classroom will connect via "
        "OAuth or a revocable token."
    )
