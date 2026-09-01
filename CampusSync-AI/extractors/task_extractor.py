import json

from prompts.task_extraction_prompt import TASK_EXTRACTION_PROMPT
from config import llm
from models.task import Task


def extract_tasks(text: str, platform: str):

    prompt = TASK_EXTRACTION_PROMPT.format(
        text=text,
        platform=platform
    )

    response = llm.invoke(prompt)

    data = json.loads(response.content)

    tasks = []

    for item in data:

        tasks.append(Task(**item))

    return tasks