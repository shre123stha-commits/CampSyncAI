from config import extraction_llm, get_logger
from models.task import Task
from prompts.task_extraction_prompt import TASK_EXTRACTION_PROMPT
from utils.llm_json import invoke_json

logger = get_logger(__name__)


def _validate(data) -> list[Task]:
    if isinstance(data, dict):
        # The model occasionally wraps the array, e.g. {"tasks": [...]}.
        for key in ("tasks", "assignments", "items", "data"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            data = [data]

    if not isinstance(data, list):
        raise ValueError("Expected a JSON array of tasks.")

    return [Task(**item) for item in data if isinstance(item, dict)]


def extract_tasks(text: str, platform: str) -> list[Task]:
    """Extract academic tasks from raw document text."""
    if not text.strip():
        logger.warning("Empty document text for platform %s", platform)
        return []

    prompt = TASK_EXTRACTION_PROMPT.format(text=text, platform=platform)

    tasks = invoke_json(
        extraction_llm,
        prompt,
        _validate,
        label=f"task_extraction[{platform}]",
    )

    logger.info("Extracted %d task(s) from %s", len(tasks), platform)

    return tasks
