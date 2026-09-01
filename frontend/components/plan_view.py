"""Shared rendering for a generated study plan, used by all four modes."""

from __future__ import annotations

import streamlit as st

from frontend.api.backend_api import BackendError, generate_plan

PRIORITY_ICON = {"High": "🔴", "Medium": "🟠", "Low": "🟢"}


def fetch_plan(student_id: str, mode: str, *, force: bool = False):
    """Fetch a plan, caching it in the session so navigation is instant.

    Returns (plan, error_message). Exactly one will be None.
    """
    cache = st.session_state.setdefault("plan_cache", {})
    key = f"{student_id}:{mode}"

    if not force and key in cache:
        return cache[key], None

    try:
        with st.spinner("🤖 AI is building your study plan…"):
            plan = generate_plan(student_id, mode)
    except BackendError as exc:
        return None, str(exc)

    cache[key] = plan
    return plan, None


def render_empty_state():
    st.success("🎉 Nothing pending — you're all caught up!")
    st.caption(
        "No academic tasks were found in your documents. "
        "New assignments will appear here once they're added."
    )


def render_plan(plan: dict, *, show_timings: bool, show_day: bool):
    """Render a plan's items as cards."""
    items = plan.get("plan") or []

    if not items:
        render_empty_state()
        return

    for task in items:
        with st.container(border=True):
            icon = PRIORITY_ICON.get(task.get("priority", ""), "🔵")

            heading = task.get("subject", "Task")
            if show_day and task.get("day"):
                heading = f"{task['day']} • {heading}"

            col1, col2 = st.columns([6, 1])
            with col1:
                st.subheader(heading)
            with col2:
                st.markdown(f"### {icon}")

            if task.get("work"):
                st.write(task["work"])

            if show_timings and task.get("start_time"):
                st.write(f"🕒 {task['start_time']} – {task.get('end_time', '')}")

            meta = []
            if task.get("deadline"):
                meta.append(f"📅 **Deadline:** {task['deadline']}")
            if task.get("days_remaining") is not None:
                meta.append(f"⏳ **Days left:** {task['days_remaining']}")
            if task.get("priority"):
                meta.append(f"🔥 **Priority:** {task['priority']}")

            if meta:
                st.markdown(" &nbsp;·&nbsp; ".join(meta))

            if task.get("reason"):
                st.caption(task["reason"])


def plan_page(title: str, mode: str, *, show_timings: bool, show_day: bool):
    """Render a full plan page including title, refresh and back navigation."""
    st.title(title)

    student_id = st.session_state.student_id

    col1, col2 = st.columns([1, 1])
    with col1:
        back = st.button("⬅ Back to Dashboard", use_container_width=True)
    with col2:
        refresh = st.button("🔄 Regenerate", use_container_width=True)

    if back:
        st.session_state.current_page = "dashboard"
        st.rerun()

    plan, error = fetch_plan(student_id, mode, force=refresh)

    if error:
        st.error(error)
        return

    render_plan(plan, show_timings=show_timings, show_day=show_day)
