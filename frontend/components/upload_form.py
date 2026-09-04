"""Document upload, shared by the dashboard and the sources page.

The upload widget lived only on the dashboard, which made the "Uploaded documents"
card on the sources page a dead end: it described a source the student could
not act on from that screen. Both pages now render the same widget.
"""

from __future__ import annotations

import streamlit as st

from frontend.api.backend_api import BackendError, upload_document

KINDS = (
    ("timetable", "Timetable"),
    ("lms", "LMS / assignments"),
)


def render_upload_controls(*, key_prefix: str = "") -> bool:
    """Render the two file pickers. Returns True if something was uploaded.

    `key_prefix` keeps Streamlit widget keys unique when the same controls are
    rendered on more than one page in a session.
    """
    uploaded_any = False
    col1, col2 = st.columns(2)

    for column, (kind, label) in zip((col1, col2), KINDS):
        with column:
            picked = st.file_uploader(
                label, type=["docx"], key=f"{key_prefix}upload_{kind}"
            )

            if picked is not None and st.button(
                f"Upload {label}",
                key=f"{key_prefix}btn_{kind}",
                use_container_width=True,
            ):
                try:
                    upload_document(
                        st.session_state.token,
                        kind,
                        picked.name,
                        picked.getvalue(),
                    )
                    st.session_state.pop("task_cache", None)
                    st.session_state.pop("plan_cache", None)
                    st.success(f"{label} uploaded.")
                    uploaded_any = True
                except BackendError as exc:
                    st.error(str(exc))

    return uploaded_any
