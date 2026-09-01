from pydantic import BaseModel


class Lecture(BaseModel):
    day: str
    start_time: str
    end_time: str
    subject: str