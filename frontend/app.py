import sys
from pathlib import Path

import streamlit as st

# Streamlit runs this file as a script, so the repo root is not on sys.path
# by default. Add it so `frontend.*` imports resolve regardless of which
# directory the app was launched from.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from frontend.components.plan_view import plan_page  # noqa: E402
from frontend.views.dashboard import show_dashboard  # noqa: E402
from frontend.views.login import show_login  # noqa: E402
from frontend.views.sources import show_sources  # noqa: E402

st.set_page_config(
    page_title="CampusSync AI",
    page_icon="🎓",
    layout="wide",
)


def load_css():
    try:
        with open(_REPO_ROOT / "frontend" / "styles" / "style.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass


load_css()

st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("student_id", "")
st.session_state.setdefault("token", "")
st.session_state.setdefault("current_page", "dashboard")


if not st.session_state.logged_in:
    show_login()

else:
    page = st.session_state.current_page

    if page == "dashboard":
        show_dashboard()

    elif page == "sources":
        show_sources()

    elif page == "today":
        plan_page(
            "📘 Today's Study Plan",
            "day_without_timings",
            show_timings=False,
            show_day=False,
        )

    elif page == "today_timed":
        plan_page(
            "⏰ Today's Timed Study Plan",
            "day_with_timings",
            show_timings=True,
            show_day=False,
        )

    elif page == "week":
        plan_page(
            "📅 Weekly Study Plan",
            "week_without_timings",
            show_timings=False,
            show_day=True,
        )

    elif page == "week_timed":
        plan_page(
            "🗓 Weekly Timed Study Plan",
            "week_with_timings",
            show_timings=True,
            show_day=True,
        )

    else:
        st.session_state.current_page = "dashboard"
        st.rerun()
