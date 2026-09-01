from pydantic import BaseModel


class PlannedTask(BaseModel):

    title: str

    subject: str

    slot: str

    reason: str


class StudyPlan(BaseModel):

    registration_no: str

    mode: str

    strategy: str

    tasks: list[PlannedTask]