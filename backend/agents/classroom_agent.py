"""Google Classroom source.

Not yet connected. When implemented this will use OAuth 2.0 (never a
password) and normalise `courses.courseWork` into the shared `Task` model,
so nothing downstream needs to change.
"""

from config import get_logger

logger = get_logger(__name__)


def classroom_agent(state):
    state.setdefault("classroom_tasks", [])

    logger.info("Classroom agent: no account connected, skipping.")

    return state
