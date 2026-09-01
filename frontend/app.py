import streamlit as st

from frontend.api.backend_api import backend_online, list_students
from frontend.components.plan_view import plan_page
from frontend.pages.dashboard import show_dashboard

st.set_page_config(
    page_title="CampusSync AI",
    page_icon="🎓",
    layout="wide",
)


def load_css():
    try:
        with open("frontend/styles/style.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass


load_css()

st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("student_id", "")
st.session_state.setdefault("current_page", "dashboard")


# ====================================================
#                   LOGIN
# ====================================================

if not st.session_state.logged_in:
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
            "⚠️ Backend not reachable. Start it with `make backend` "
            "and make sure Ollama is running."
        )

    known = list_students()

    if known:
        st.caption("Demo accounts available: " + ", ".join(known))

    student_id = st.text_input(
        "Student ID", placeholder="e.g. 24BAI1127"
    ).strip()

    if st.button("Login", use_container_width=True):
        if not student_id:
            st.warning("Please enter your Student ID.")
        elif known and student_id not in known:
            st.error(
                f"No records found for '{student_id}'. "
                f"Try one of: {', '.join(known)}"
            )
        else:
            st.session_state.student_id = student_id
            st.session_state.logged_in = True
            st.session_state.current_page = "dashboard"
            st.rerun()


# ====================================================
#                MAIN APPLICATION
# ====================================================

else:
    page = st.session_state.current_page

    if page == "dashboard":
        show_dashboard()

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
