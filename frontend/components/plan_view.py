"""Shared rendering for a generated study plan, used by all four modes."""

from __future__ import annotations

import streamlit as st

from frontend.api.backend_api import AuthError, BackendError, generate_my_plan

PRIORITY_ICON = {"High": "🔴", "Medium": "🟠", "Low": "🟢"}


def fetch_plan(mode: str, *, force: bool = False, feedback: str = ""):
    """Fetch a plan for the signed-in student, cached per mode in the session.

    `feedback` always forces a regeneration - the cached plan is by definition
    the one the student is asking to change.

    Returns (plan, error_message). Exactly one will be None.
    """
    cache = st.session_state.setdefault("plan_cache", {})

    if not force and not feedback and mode in cache:
        return cache[mode], None

    spinner = (
        "🤖 Rebuilding your plan around your feedback…"
        if feedback
        else "🤖 AI is building your study plan…"
    )

    try:
        with st.spinner(spinner):
            plan = generate_my_plan(st.session_state.token, mode, feedback)
    except (AuthError, BackendError) as exc:
        return None, str(exc)

    cache[mode] = plan
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


EXAMPLE_FEEDBACK = (
    "e.g. I have football practice Friday evening — move that work earlier"
)


def render_feedback_form(mode: str) -> str:
    """Let the student steer the next generation. Returns their note, or ""."""
    with st.expander("💬 Not quite right? Tell the planner what to change"):
        st.caption(
            "The plan is a suggestion, not an instruction. Describe what does "
            "not fit and it will be rebuilt around you. Deadlines and "
            "priorities stay accurate either way."
        )

        note = st.text_area(
            "What should change?",
            key=f"feedback_input_{mode}",
            placeholder=EXAMPLE_FEEDBACK,
            max_chars=500,
            label_visibility="collapsed",
        )

        submitted = st.button(
            "✨ Rebuild my plan",
            key=f"feedback_submit_{mode}",
            use_container_width=True,
            disabled=not note.strip(),
        )

        if submitted and note.strip():
            return note.strip()

    return ""


def plan_page(title: str, mode: str, *, show_timings: bool, show_day: bool):
    """Render a full plan page including title, refresh and back navigation."""
    st.title(title)

    col1, col2 = st.columns([1, 1])
    with col1:
        back = st.button("⬅ Back to Dashboard", use_container_width=True)
    with col2:
        refresh = st.button("🔄 Regenerate", use_container_width=True)

    if back:
        st.session_state.current_page = "dashboard"
        st.rerun()

    feedback = render_feedback_form(mode)

    plan, error = fetch_plan(mode, force=refresh, feedback=feedback)

    if error:
        st.error(error)
        return

    if feedback:
        st.success(f"✅ Rebuilt around your note: *{feedback}*")

    render_plan(plan, show_timings=show_timings, show_day=show_day)
