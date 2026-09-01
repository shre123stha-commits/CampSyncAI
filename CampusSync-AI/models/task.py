from pydantic import BaseModel


class Task(BaseModel):
    subject: str
    task_type: str
    platform: str
    deadline: str
    work: str
    days_remaining: int = 0