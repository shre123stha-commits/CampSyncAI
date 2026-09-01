import json

from config import llm
from models.timetable import Lecture
from prompts.timetable_extraction_prompt import TIMETABLE_EXTRACTION_PROMPT


def extract_timetable(text: str):

    prompt = TIMETABLE_EXTRACTION_PROMPT.format(
        text=text
    )

    response = llm.invoke(prompt)

    data = json.loads(response.content)

    lectures = [
        Lecture(**item)
        for item in data
    ]

    return lectures