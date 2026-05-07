from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class TelemetryIn(BaseModel):
    type: str                          # active | idle | unproductive
    app_name: Optional[str] = None
    window_title: Optional[str] = None
    url: Optional[str] = None
    file_path: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: int = 0                  # seconds


class TelemetryOut(BaseModel):
    message: str
    activity_id: int


class IdleReasonIn(BaseModel):
    idle_log_id: int
    reason: str
