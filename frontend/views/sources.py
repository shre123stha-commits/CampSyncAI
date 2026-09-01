"""Connect external data sources.

Every option here is OAuth or a revocable, student-supplied URL. The page
says so explicitly — it is a deliberate part of the product, not a footnote.
"""

import streamlit as st

from frontend.api.backend_api import (
    BackendError,
    connect_classroom,
    connect_ics,
    disconnect_source,
    list_sources,
)
from frontend.components.upload_form import render_upload_controls

ICON = {
    "document": "📄",
    "ics": "📅",
    "classroom": "🎓",
}


def _clear_caches():
    st.session_state.pop("task_cache", None)
    st.session_state.pop("plan_cache", None)


def show_sources():
    st.title("🔗 Connect your accounts")

    st.info(
        "🔒 **We never ask for your university password.** Every integration "
        "uses either a file you upload, a revocable calendar link, or Google's "
        "own sign-in screen. You can disconnect any source at any time.",
        icon="🔒",
    )

    if st.button("⬅ Back to Dashboard"):
        st.session_state.current_page = "dashboard"
        st.rerun()

    st.divider()

    try:
        sources = list_sources(st.session_state.token)["sources"]
    except BackendError as exc:
        st.error(str(exc))
        return

    for source in sources:
        kind = source["type"]

        with st.container(border=True):
            col1, col2 = st.columns([4, 1])

            with col1:
                st.subheader(f"{ICON.get(kind, '🔌')} {source['name']}")
                if kind != "document":
                    st.caption(source["note"])

            with col2:
                if kind == "document":
                    # Documents are not an account you connect to; the path is
                    # always open. "Not connected" read as a broken feature.
                    st.success("Always on")
                elif source["connected"]:
                    st.success("Connected")
                elif not source["available"]:
                    st.caption("Unavailable")
                else:
                    st.caption("Not connected")

            if source["last_error"]:
                st.warning(f"Last sync problem: {source['last_error']}")

            if source["last_synced"]:
                st.caption(f"Last synced: {source['last_synced'][:19]}")

            # ---------------- per-source controls ----------------

            if kind == "document":
                st.caption(
                    "Always available, no credentials required. Your files "
                    "override the sample data."
                )

                if render_upload_controls(key_prefix="src_"):
                    _clear_caches()
                    st.rerun()

            elif kind == "ics":
                if source["connected"]:
                    if st.button("Disconnect", key="dc_ics"):
                        try:
                            disconnect_source(st.session_state.token, "ics")
                            _clear_caches()
                            st.rerun()
                        except BackendError as exc:
                            st.error(str(exc))
                else:
                    with st.form("ics_form"):
                        url = st.text_input(
                            "Calendar URL",
                            placeholder="https://lms.university.edu/calendar/export/…",
                        )
                        st.caption(
                            "Find this in your LMS under Calendar → Export → "
                            "Get calendar URL. It works with Moodle, Canvas, "
                            "Blackboard and Google Calendar."
                        )

                        if st.form_submit_button("Connect calendar"):
                            if not url.strip():
                                st.warning("Please paste your calendar URL.")
                            else:
                                try:
                                    result = connect_ics(
                                        st.session_state.token, url.strip()
                                    )
                                    _clear_caches()
                                    st.success(
                                        f"Connected — found "
                                        f"{result['tasks_found']} item(s)."
                                    )
                                    st.rerun()
                                except BackendError as exc:
                                    st.error(str(exc))

            elif kind == "classroom":
                if source["connected"]:
                    if st.button("Disconnect", key="dc_classroom"):
                        try:
                            disconnect_source(
                                st.session_state.token, "classroom"
                            )
                            _clear_caches()
                            st.rerun()
                        except BackendError as exc:
                            st.error(str(exc))

                elif not source["available"]:
                    # On a student-run instance the "administrator" is the
                    # student, so point at the fix rather than at someone else.
                    st.caption(
                        "Needs Google OAuth credentials before it can be "
                        "switched on. Add GOOGLE_CLIENT_ID and "
                        "GOOGLE_CLIENT_SECRET to a `.env` file in the project "
                        "root and restart the backend."
                    )
                    st.caption(
                        "Step-by-step guide: "
                        "`docs/GOOGLE_CLASSROOM_SETUP.md`"
                    )

                else:
                    if st.button("Connect Google Classroom", key="go_classroom"):
                        try:
                            url = connect_classroom(st.session_state.token)[
                                "authorization_url"
                            ]
                            st.link_button(
                                "Continue to Google →",
                                url,
                                use_container_width=True,
                            )
                            st.caption(
                                "Sign in on Google's page, then return here "
                                "and refresh."
                            )
                        except BackendError as exc:
                            st.error(str(exc))

    st.divider()

    st.caption(
        "Coming soon: Moodle and Canvas via a student-generated API token "
        "(also revocable, also not a password)."
    )
