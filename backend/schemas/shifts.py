from datetime import datetime, time

from pydantic import BaseModel, Field


class ShiftBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    start_time: time
    end_time: time
    timezone: str = Field(default="Asia/Kolkata", max_length=64)
    grace_minutes: int = Field(default=10, ge=0, le=240)
    is_overnight: int = Field(default=0, ge=0, le=1)


class ShiftCreate(ShiftBase):
    pass


class ShiftUpdate(ShiftBase):
    pass


class ShiftOut(ShiftBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ShiftListResponse(BaseModel):
    items: list[ShiftOut]
