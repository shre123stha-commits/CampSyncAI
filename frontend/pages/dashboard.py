import streamlit as st

from frontend.api.backend_api import BackendError, get_tasks, refresh_student
from frontend.components.assignment_card import assignment_card
from frontend.components.plan_view import render_empty_state
from frontend.components.planner_cards import planner_cards


def load_tasks(student_id: str, *, force: bool = False):
    """Tasks for the dashboard. No planning call, so this is fast."""
    cache = st.session_state.setdefault("task_cache", {})

    if not force and student_id in cache:
        return cache[student_id], None

    try:
        with st.spinner("📚 Loading your academic data…"):
            data = get_tasks(student_id)
    except BackendError as exc:
        return None, str(exc)

    cache[student_id] = data
    return data, None


def show_dashboard():
    student_id = st.session_state.student_id

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
            try:
                refresh_student(student_id)
            except BackendError:
                pass
            st.session_state.pop("task_cache", None)
            st.session_state.pop("plan_cache", None)
            st.rerun()

    with col_b:
        if st.button("🚪 Log out", use_container_width=True):
            for key in ("logged_in", "student_id", "plan_cache", "task_cache"):
                st.session_state.pop(key, None)
            st.rerun()

    st.divider()

    data, error = load_tasks(student_id)

    if error:
        st.error(error)
        st.info(
            "Start the backend with `make backend` and make sure Ollama is "
            "running."
        )
        return

    tasks = data.get("tasks") or []

    # ----------------------------------------------------
    # SUMMARY
    # ----------------------------------------------------

    high_priority = sum(1 for t in tasks if t.get("priority") == "High")

    days = [
        t["days_remaining"]
        for t in tasks
        if isinstance(t.get("days_remaining"), int) and t["days_remaining"] < 999
    ]
    next_deadline = min(days) if days else None

    col1, col2, col3 = st.columns(3)
    col1.metric("📚 Total Tasks", len(tasks))
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
    # TODAY'S FOCUS  (most urgent task - no LLM needed)
    # ----------------------------------------------------

    st.markdown("## 🎯 Today's Focus")

    top = tasks[0]

    with st.container(border=True):
        st.success(f"🔥 {top.get('subject', 'Your next task')}")

        if top.get("work"):
            st.write(top["work"])

        meta = []
        if top.get("deadline"):
            meta.append(f"📅 **Deadline:** {top['deadline']}")
        if top.get("days_remaining") is not None:
            meta.append(f"⏳ **Days left:** {top['days_remaining']}")
        if top.get("priority"):
            meta.append(f"🔥 **Priority:** {top['priority']}")

        if meta:
            st.markdown(" &nbsp;·&nbsp; ".join(meta))

    st.divider()

    # ----------------------------------------------------
    # ASSIGNMENTS
    # ----------------------------------------------------

    st.markdown("## 📋 Assignments")

    for task in tasks:
        assignment_card(
            title=task.get("subject", "Task"),
            due=task.get("deadline", "—"),
            source=task.get("platform", "LMS"),
            priority=task.get("priority", "Medium"),
        )

    st.divider()

    planner_cards()

    st.divider()

    st.caption("CampusSync AI • Ollama • LangGraph • FastAPI")
