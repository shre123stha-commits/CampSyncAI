import streamlit as st

from frontend.api.backend_api import (
    AuthError,
    BackendError,
    get_tasks,
    logout,
    refresh_data,
    set_task_completed,
)
from frontend.components.deadline_text import format_days_remaining
from frontend.components.plan_view import render_empty_state
from frontend.components.planner_cards import planner_cards
from frontend.components.upload_form import render_upload_controls

PRIORITY_ICON = {"High": "🔴", "Medium": "🟠", "Low": "🟢"}


def _sign_out():
    logout(st.session_state.get("token", ""))
    for key in (
        "logged_in",
        "student_id",
        "token",
        "name",
        "plan_cache",
        "task_cache",
    ):
        st.session_state.pop(key, None)
    st.rerun()


def load_tasks(*, force: bool = False):
    """Tasks for the dashboard. No planning call, so this is fast."""
    if not force and "task_cache" in st.session_state:
        return st.session_state.task_cache, None

    try:
        with st.spinner("📚 Loading your academic data…"):
            data = get_tasks(st.session_state.token)
    except AuthError:
        _sign_out()
        return None, None
    except BackendError as exc:
        return None, str(exc)

    st.session_state.task_cache = data
    return data, None


def _upload_expander():
    with st.expander("📤 Upload your documents"):
        st.caption(
            "Upload your own timetable or LMS export (.docx). Your files "
            "override the sample data. No university password required."
        )

        if render_upload_controls():
            st.rerun()


def _task_row(task):
    """One task with a completion checkbox."""
    done = task["completed"]

    col1, col2 = st.columns([1, 11])

    with col1:
        checked = st.checkbox(
            "Done",
            value=done,
            key=f"task_{task['id']}",
            label_visibility="collapsed",
        )

    with col2:
        icon = PRIORITY_ICON.get(task.get("priority", ""), "🔵")
        title = task.get("subject", "Task")

        if done:
            st.markdown(f"~~**{title}**~~ &nbsp; ✅")
        else:
            st.markdown(f"**{title}** &nbsp; {icon}")

        details = []
        if task.get("deadline"):
            details.append(f"📅 {task['deadline']}")
        if not done and isinstance(task.get("days_remaining"), int):
            phrase = format_days_remaining(task["days_remaining"])
            if phrase:
                details.append(phrase)
        if task.get("platform"):
            details.append(f"📚 {task['platform']}")

        if details:
            st.caption(" · ".join(details))

        if task.get("work") and not done:
            st.caption(task["work"])

    if checked != done:
        try:
            set_task_completed(st.session_state.token, task["id"], checked)
            st.session_state.pop("task_cache", None)
            st.session_state.pop("plan_cache", None)
            st.rerun()
        except BackendError as exc:
            st.error(str(exc))


def show_dashboard():
    name = st.session_state.get("name") or st.session_state.student_id

    st.markdown(
        f"""
        <div class="main-title">🎓 CampusSync AI</div>
        <div class="subtitle">Your AI Academic Assistant</div>
        <br>
        <div class="welcome">Welcome back, <b>{name}</b> 👋</div>
        <br>
        """,
        unsafe_allow_html=True,
    )

    col_a, col_src, col_b = st.columns([1, 1, 1])

    with col_src:
        if st.button("🔗 Connect accounts", use_container_width=True):
            st.session_state.current_page = "sources"
            st.rerun()

    with col_a:
        if st.button("🔄 Refresh data", use_container_width=True):
            try:
                refresh_data(st.session_state.token)
            except BackendError:
                pass
            st.session_state.pop("task_cache", None)
            st.session_state.pop("plan_cache", None)
            st.rerun()

    with col_b:
        if st.button("🚪 Log out", use_container_width=True):
            _sign_out()

    st.divider()

    data, error = load_tasks()

    if error:
        st.error(error)
        st.info("Start the backend with `make backend`.")
        return

    if data is None:
        return

    tasks = data.get("tasks") or []
    stats = data.get("stats", {})

    for problem in data.get("source_errors") or []:
        st.warning(f"⚠️ {problem}")

    _upload_expander()

    st.divider()

    # ----------------------------------------------------
    # SUMMARY
    # ----------------------------------------------------

    pending = [t for t in tasks if not t["completed"]]

    days = [
        t["days_remaining"]
        for t in pending
        if isinstance(t.get("days_remaining"), int) and t["days_remaining"] < 999
    ]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📚 Total", stats.get("total", len(tasks)))
    col2.metric("✅ Done", stats.get("completed", 0))
    col3.metric(
        "🔥 High Priority",
        sum(1 for t in pending if t.get("priority") == "High"),
    )
    col4.metric(
        "⏳ Next Deadline", f"{min(days)} days" if days else "—"
    )

    if tasks:
        st.progress(
            stats.get("completed", 0) / max(len(tasks), 1),
            text=f"{stats.get('completed', 0)} of {len(tasks)} complete",
        )

    st.divider()

    if not tasks:
        render_empty_state()
        st.info(
            "Upload your timetable and LMS documents above to get started."
        )
        return

    # ----------------------------------------------------
    # TODAY'S FOCUS
    # ----------------------------------------------------

    if pending:
        st.markdown("## 🎯 Today's Focus")

        top = pending[0]

        with st.container(border=True):
            st.success(f"🔥 {top.get('subject', 'Your next task')}")

            if top.get("work"):
                st.write(top["work"])

            meta = []
            if top.get("deadline"):
                meta.append(f"📅 **Deadline:** {top['deadline']}")
            if isinstance(top.get("days_remaining"), int):
                meta.append(f"⏳ **Days left:** {top['days_remaining']}")
            if top.get("priority"):
                meta.append(f"🔥 **Priority:** {top['priority']}")

            if meta:
                st.markdown(" &nbsp;·&nbsp; ".join(meta))
    else:
        st.success("🎉 Everything is done. Nice work!")

    st.divider()

    # ----------------------------------------------------
    # TASK LIST
    # ----------------------------------------------------

    st.markdown("## 📋 Your Tasks")
    st.caption("Tick a task to mark it complete — plans skip finished work.")

    for task in tasks:
        with st.container(border=True):
            _task_row(task)

    st.divider()

    planner_cards()

    st.divider()

    st.caption("CampusSync AI • Ollama • LangGraph • FastAPI")
