import streamlit as st

from frontend.components.assignment_card import assignment_card
from frontend.components.planner_cards import planner_cards
from frontend.api.backend_api import generate_plan


def show_dashboard():
    with st.spinner("🤖 AI is generating your personalized study plan..."):

        plan = generate_plan(
            st.session_state.student_id,
            "day_without_timings"
        )

    tasks = plan["plan"]

    total_tasks = len(tasks)

    high_priority = len(
    [t for t in tasks if t["priority"] == "High"])

    next_deadline = min(
    t["days_remaining"] for t in tasks)

    #plan = generate_plan(
     #   st.session_state.student_id,
      #  "day_without_timings"
    #)
    #plan = {
    #"plan": []


    # ----------------------------------------------------
    # HERO SECTION
    # ----------------------------------------------------

    st.markdown(
        f"""
        <div class="main-title">
            🎓 CampusSync AI
        </div>

        <div class="subtitle">
            Your AI Academic Assistant
        </div>

        <br>

        <div class="welcome">
            Welcome back,
            <b>{st.session_state.student_id}</b> 👋
        </div>

        <div class="status">
            🟢 AI Connected &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;
            📚 4 Sources Connected
        </div>

        <br>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    # ----------------------------------------------------
    # SUMMARY
    # ----------------------------------------------------

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "📚 Total Tasks",
            total_tasks
        )

    with col2:
        st.metric(
            "🔥 High Priority",
            high_priority
        )

    with col3:
        st.metric(
            "⏳ Next Deadline",
            f"{next_deadline} days"
        )

    st.divider()

    # ----------------------------------------------------
    # TODAY'S FOCUS
    # ----------------------------------------------------

    st.markdown("## 🎯 Today's Focus")

    top = tasks[0]

    with st.container(border=True):

        st.subheader("🎯 Today's Focus")

        st.success(f"🔥 {top['subject']}")

        st.write(f"📅 Deadline: {top['deadline']}")

        st.write(f"🔥 Priority: {top['priority']}")

        st.info(top["reason"])

    st.divider()

    # ----------------------------------------------------
    # ASSIGNMENTS
    # ----------------------------------------------------

    st.markdown("## 📋 Assignments")

    for task in plan["plan"]:

        assignment_card(
            title=task["subject"],
            due=task["deadline"],
            source="LMS",
            priority=task["priority"]
        )

    st.divider()

    # ----------------------------------------------------
    # AI STUDY PLANNER
    # ----------------------------------------------------

    planner_cards()

    st.divider()

    st.caption(
        "CampusSync AI • Powered by Ollama • LangGraph • FastAPI • Google Classroom"
    )