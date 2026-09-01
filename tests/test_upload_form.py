"""The shared upload widget must be usable from every page that shows it.

Regression: "Uploaded documents" appeared on the sources page with a
"Not connected" badge and a note telling the student to go somewhere else,
so the card described a source it gave no way to act on.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# These modules import streamlit, which is a frontend dependency and is not
# installed in the backend-only environment CI uses for the test job.
pytest.importorskip("streamlit", reason="frontend dependency not installed")

from frontend.components import upload_form  # noqa: E402
from frontend.views import dashboard, sources  # noqa: E402


def test_both_document_kinds_are_offered():
    kinds = dict(upload_form.KINDS)

    assert set(kinds) == {"timetable", "lms"}


def test_dashboard_and_sources_share_one_implementation():
    """Two copies of an upload flow would drift; there must be exactly one."""
    assert dashboard.render_upload_controls is upload_form.render_upload_controls
    assert sources.render_upload_controls is upload_form.render_upload_controls


def test_key_prefix_keeps_widget_keys_unique():
    """Streamlit raises if two widgets in a session share a key.

    The sources page passes a prefix precisely so the dashboard's pickers and
    its own can coexist.
    """
    import inspect

    signature = inspect.signature(upload_form.render_upload_controls)

    assert "key_prefix" in signature.parameters
    assert signature.parameters["key_prefix"].default == ""


def test_sources_page_renders_the_uploader():
    source = inspect_source(sources.show_sources)

    assert "render_upload_controls" in source


def test_sources_page_no_longer_redirects_to_the_dashboard():
    source = inspect_source(sources.show_sources)

    assert "Upload documents from the dashboard" not in source


def test_document_card_is_not_labelled_not_connected():
    """Documents are always available, not an account you connect to."""
    source = inspect_source(sources.show_sources)

    assert "Always on" in source


def test_classroom_unavailable_message_points_at_the_fix():
    """A student running their own instance is the administrator."""
    source = inspect_source(sources.show_sources)

    assert "GOOGLE_CLIENT_ID" in source
    assert "GOOGLE_CLASSROOM_SETUP" in source
    assert "server administrator has not" not in source


def inspect_source(func) -> str:
    import inspect

    return inspect.getsource(func)
