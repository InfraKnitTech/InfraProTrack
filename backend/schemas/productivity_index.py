from datetime import datetime

from pydantic import BaseModel


class ProductivityIndexRow(BaseModel):
    employee_id: int
    employee_name: str
    username: str
    date: datetime
    score: int
    productive_pct: int
    idle_pct: int
    unproductive_pct: int
    login_time: datetime | None
    logout_time: datetime | None


class ProductivityIndexSummaryResponse(BaseModel):
    average_score: float
    employee_count: int
    rows: list[ProductivityIndexRow]


class ProductivityIndexRecalculateResponse(BaseModel):
    recalculated: int
    rows: list[ProductivityIndexRow]
