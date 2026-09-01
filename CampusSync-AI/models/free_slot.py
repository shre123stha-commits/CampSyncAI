from pydantic import BaseModel


class FreeSlot(BaseModel):
    day: str
    slot_type: str
    start_time: str
    end_time: str