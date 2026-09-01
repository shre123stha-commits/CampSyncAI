from config import extraction_llm, get_logger
from models.timetable import Lecture
from prompts.timetable_extraction_prompt import TIMETABLE_EXTRACTION_PROMPT
from utils.llm_json import invoke_json

logger = get_logger(__name__)


def _validate(data) -> list[Lecture]:
    if isinstance(data, dict):
        for key in ("timetable", "lectures", "schedule", "data"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            data = [data]

    if not isinstance(data, list):
        raise ValueError("Expected a JSON array of lectures.")

    return [Lecture(**item) for item in data if isinstance(item, dict)]


def extract_timetable(text: str) -> list[Lecture]:
    """Extract the lecture timetable from raw document text."""
    if not text.strip():
        logger.warning("Empty timetable document text")
        return []

    prompt = TIMETABLE_EXTRACTION_PROMPT.format(text=text)

    lectures = invoke_json(
        extraction_llm,
        prompt,
        _validate,
        label="timetable_extraction",
    )

    logger.info("Extracted %d lecture(s)", len(lectures))

    return lectures
