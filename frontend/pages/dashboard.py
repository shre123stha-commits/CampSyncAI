import streamlit as st

from frontend.components.assignment_card import assignment_card
from frontend.components.plan_view import fetch_plan, render_empty_state
from frontend.components.planner_cards import planner_cards


def show_dashboard():
    student_id = st.session_state.student_id

    # ----------------------------------------------------
    # HERO
    # ----------------------------------------------------

    st.markdown(
        f"""
        <div class="main-title">🎓 CampusSync AI</div>
        <div class="subtitle">Your AI Academic Assistant</div>
        <br>
        <div class="welcome">Welcome back, <b>{student_id}</b> 👋</div>
        <br>
        """,
        unsafe_allow_html=True,
    )

    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("🔄 Refresh data", use_container_width=True):
            st.session_state.pop("plan_cache", None)
            st.rerun()
    with col_b:
        if st.button("🚪 Log out", use_container_width=True):
            for key in ("logged_in", "student_id", "plan_cache"):
                st.session_state.pop(key, None)
            st.rerun()

    st.divider()

    plan, error = fetch_plan(student_id, "day_without_timings")

    if error:
        st.error(error)
        st.info(
            "Start the backend with `make backend` (or `docker compose up`) "
            "and make sure Ollama is running."
        )
        return

    tasks = plan.get("plan") or []

    # ----------------------------------------------------
    # SUMMARY
    # ----------------------------------------------------

    total_tasks = len(tasks)
    high_priority = sum(1 for t in tasks if t.get("priority") == "High")

    days = [
        t["days_remaining"]
        for t in tasks
        if isinstance(t.get("days_remaining"), int)
    ]
    next_deadline = min(days) if days else None

    col1, col2, col3 = st.columns(3)
    col1.metric("📚 Total Tasks", total_tasks)
    col2.metric("🔥 High Priority", high_priority)
    col3.metric(
        "⏳ Next Deadline",
        f"{next_deadline} days" if next_deadline is not None else "—",
    )

    st.divider()

    if not tasks:
        render_empty_state()
        st.divider()
        planner_cards()
        return

    # ----------------------------------------------------
    # TODAY'S FOCUS
    # ----------------------------------------------------

    st.markdown("## 🎯 Today's Focus")

    top = tasks[0]

    with st.container(border=True):
        st.success(f"🔥 {top.get('subject', 'Your next task')}")

        if top.get("work"):
            st.write(top["work"])

        if top.get("deadline"):
            st.write(f"📅 Deadline: {top['deadline']}")

        if top.get("priority"):
            st.write(f"🔥 Priority: {top['priority']}")

        if top.get("reason"):
            st.info(top["reason"])

    st.divider()

    # ----------------------------------------------------
    # ASSIGNMENTS
    # ----------------------------------------------------

    st.markdown("## 📋 Assignments")

    for task in tasks:
        assignment_card(
            title=task.get("subject", "Task"),
            due=task.get("deadline", "—"),
            source="LMS",
            priority=task.get("priority", "Medium"),
        )

    st.divider()

    planner_cards()

    st.divider()

    st.caption("CampusSync AI • Ollama • LangGraph • FastAPI")
