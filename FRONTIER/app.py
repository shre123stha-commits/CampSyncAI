import streamlit as st
from frontend.pages.dashboard import show_dashboard
from frontend.api.backend_api import generate_plan


# ---------------- Page Configuration ---------------- #

st.set_page_config(
    page_title="CampusSync AI",
    page_icon="🎓",
    layout="wide"
)


# ---------------- Load CSS ---------------- #

def load_css():
    with open("frontend/styles/style.css") as f:
        st.markdown(
            f"<style>{f.read()}</style>",
            unsafe_allow_html=True
        )


load_css()


# ---------------- Session State ---------------- #

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "student_id" not in st.session_state:
    st.session_state.student_id = ""

if "current_page" not in st.session_state:
    st.session_state.current_page = "dashboard"


# ====================================================
#                   LOGIN PAGE
# ====================================================

if not st.session_state.logged_in:

    st.markdown("""
    <div class="main-title">
        🎓 CampusSync AI
    </div>

    <div class="subtitle">
        Your AI Academic Assistant
    </div>
    """, unsafe_allow_html=True)

    st.write("")

    student_id = st.text_input(
        "Student ID",
        placeholder="Enter your Student ID"
    )

    st.write("")

    if st.button("Login", use_container_width=True):

        if student_id.strip() == "":
            st.warning("Please enter your Student ID.")

        else:

            st.session_state.student_id = student_id
            st.session_state.logged_in = True

            st.rerun()


# ====================================================
#                  MAIN APPLICATION
# ====================================================

else:

    if st.session_state.current_page == "dashboard":

        show_dashboard()

    elif st.session_state.current_page == "today":

        st.title("📘 Today's Study Plan")

        plan = generate_plan(
            st.session_state.student_id,
            "day_without_timings"
        )

        for task in plan["plan"]:

            with st.container(border=True):

                st.subheader(task["subject"])

                st.write(task["work"])

                st.write(f"📅 Deadline: {task['deadline']}")

                st.write(f"⏳ Days Remaining: {task['days_remaining']}")

                st.write(f"🔥 Priority: {task['priority']}")

                st.caption(task["reason"])

        if st.button("⬅ Back to Dashboard"):

            st.session_state.current_page = "dashboard"

            st.rerun()

    elif st.session_state.current_page == "today_timed":

        st.title("⏰ Today's Timed Study Plan")

        with st.spinner("🤖 AI is generating your study plan..."):

            plan = generate_plan(
                st.session_state.student_id,
                "day_with_timings"
            )

        for task in plan["plan"]:

            with st.container(border=True):

                st.subheader(task["subject"])

                st.write(task["work"])

                st.write(f"🕒 {task['start_time']} - {task['end_time']}")

                st.write(f"📅 Deadline: {task['deadline']}")

                st.write(f"🔥 Priority: {task['priority']}")

                st.caption(task["reason"])

        if st.button("⬅ Back to Dashboard"):

            st.session_state.current_page = "dashboard"

            st.rerun()

    elif st.session_state.current_page == "week":

        st.title("📅 Weekly Study Plan")

        with st.spinner("🤖 AI is generating your study plan..."):

            plan = generate_plan(
                st.session_state.student_id,
                "week_without_timings"
            )

        for task in plan["plan"]:

            with st.container(border=True):

                st.subheader(f"{task['day']} • {task['subject']}")

                st.write(task["work"])

                st.write(f"📅 Deadline: {task['deadline']}")

                st.write(f"🔥 Priority: {task['priority']}")

                st.caption(task["reason"])

        if st.button("⬅ Back to Dashboard"):

            st.session_state.current_page = "dashboard"

            st.rerun()

    elif st.session_state.current_page == "week_timed":

        st.title("🗓 Weekly Timed Study Plan")

        with st.spinner("🤖 AI is generating your study plan..."):

            plan = generate_plan(
                st.session_state.student_id,
                "week_with_timings"
            )

        for task in plan["plan"]:

            with st.container(border=True):

                st.subheader(f"{task['day']} • {task['subject']}")

                st.write(task["work"])

                st.write(f"🕒 {task['start_time']} - {task['end_time']}")

                st.write(f"📅 Deadline: {task['deadline']}")

                st.write(f"🔥 Priority: {task['priority']}")

                st.caption(task["reason"])

        if st.button("⬅ Back to Dashboard"):

            st.session_state.current_page = "dashboard"

            st.rerun()