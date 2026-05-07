from datetime import datetime

from pydantic import BaseModel


class ProductivitySummaryRow(BaseModel):
    group_by: str
    group_id: int | None
    group_name: str
    employee_count: int
    login_count: int
    logout_count: int
    first_login: datetime | None
    last_logout: datetime | None
    productive_seconds: int
    unproductive_seconds: int
    active_seconds: int
    idle_seconds: int
    total_tracked_seconds: int
    productivity_percent: float


class ProductivitySummaryResponse(BaseModel):
    group_by: str
    start_date: str | None
    end_date: str | None
    rows: list[ProductivitySummaryRow]
