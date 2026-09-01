TASK_EXTRACTION_PROMPT = """
You are an academic information extraction assistant.

Extract every academic task from the following text.

A task can be:

- Assignment
- Quiz
- Lab
- Project
- Viva
- Presentation
- Tutorial

Return ONLY valid JSON.

Schema:

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
5. Platform is always "{platform}".
6. Put the actual work the student has to perform in the "work" field.
7. Normalize task_type to values like Assignment, Quiz, Lab Report, Project, Field Record, etc.

Platform:
{platform}

Document:

{text}
"""