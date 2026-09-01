from pathlib import Path

from config import llm
from utils.doc_loader import read_docx

text = read_docx(
    Path("data/documents/lms/24BME1001.docx")
)

prompt = f"""
You are an academic information extraction assistant.

The following document is from an LMS.

Extract EVERY academic task.

A task can be:
- Assignment
- Quiz
- Lab
- Project
- Viva
- Presentation

Return ONLY valid JSON.

Schema:

[
    {{
        "subject":"",
        "task_type":"",
        "platform":"",
        "deadline":"",
        "work":""
    }}
]

Rules:

1. Return ONLY valid JSON.
2. Do NOT explain anything.
3. Do NOT invent information.
4. Copy deadlines exactly as written.
5. Platform is always "{"platform"}".
6. Put the actual work the student has to perform in the "work" field.
7. Normalize task_type to values like Assignment, Quiz, Lab Report, Project, Field Record, etc.


Document:

{text}
"""

response = llm.invoke(prompt)

print(response.content)