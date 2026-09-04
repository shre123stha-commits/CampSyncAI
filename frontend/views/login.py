"""Login and registration.

These credentials are for CampusSync AI only. We never ask for a university
password — external platforms will connect via OAuth or a revocable token.
"""

import streamlit as st

from frontend.api.backend_api import (
    BackendError,
    backend_online,
    login,
    register,
    reset_password,
)


def _store_session(result: dict):
    st.session_state.token = result["token"]
    st.session_state.student_id = result["registration_no"]
    st.session_state.name = result.get("name", "")
    st.session_state.logged_in = True
    st.session_state.current_page = "dashboard"


def _show_recovery_code(code: str):
    """Display the one-time recovery code. It can never be shown again."""
    st.success("✅ Account ready")

    st.warning(
        "**Save this recovery code now.** It is the only way to get back "
        "into your account if you forget your password, and it will never "
        "be shown again.",
        icon="🔑",
    )

    st.code(code, language=None)

    st.caption(
        "Screenshot it, or put it in your notes app. Treat it like a "
        "password - anyone who has it can reset your account."
    )

    if st.button("I have saved it - continue", use_container_width=True):
        st.session_state.logged_in = True
        st.session_state.current_page = "dashboard"
        st.rerun()


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

    # A recovery code must be shown *after* the rerun that logs the student
      # in, otherwise it flashes past. Held in session state for one render.
    pending_code = st.session_state.pop("new_recovery_code", None)

    if pending_code:
        _show_recovery_code(pending_code)
        return

    sign_in, sign_up, forgot = st.tabs(
        ["Sign in", "Create account", "Forgot password"]
    )

    with sign_in, st.form("login_form"):
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

    with sign_up, st.form("register_form"):
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
                    result = register(
                        new_reg.strip(), new_password, new_name.strip()
                    )
                    _store_session(result)

                    if result.get("recovery_code"):
                        st.session_state.new_recovery_code = result[
                            "recovery_code"
                        ]
                        st.session_state.logged_in = False

                    st.rerun()
                except BackendError as exc:
                    st.error(str(exc))

    with forgot:
        st.caption(
            "Enter the recovery code you saved when you created your "
            "account. There is no email reset - the code is the only way in."
        )

        with st.form("reset_form"):
            r_reg = st.text_input(
                "Registration number", placeholder="24BAI1127", key="rst_reg"
            )
            r_code = st.text_input(
                "Recovery code", placeholder="K7QM-2XPD-9WRT-BH4N", key="rst_code"
            )
            r_pw = st.text_input("New password", type="password", key="rst_pw")
            r_pw2 = st.text_input(
                "Confirm new password", type="password", key="rst_pw2"
            )

            if st.form_submit_button("Reset password", use_container_width=True):
                if not r_reg.strip() or not r_code.strip():
                    st.warning("Registration number and recovery code are required.")
                elif len(r_pw) < 6:
                    st.warning("Password must be at least 6 characters.")
                elif r_pw != r_pw2:
                    st.error("Passwords do not match.")
                else:
                    try:
                        result = reset_password(
                            r_reg.strip(), r_code.strip(), r_pw
                        )
                        st.session_state.new_recovery_code = result[
                            "recovery_code"
                        ]
                        st.rerun()
                    except BackendError as exc:
                        st.error(str(exc))

    st.divider()

    st.caption(
        "🔒 This password is for CampusSync AI only. We never ask for your "
        "university password — LMS and Google Classroom will connect via "
        "OAuth or a revocable token."
    )
