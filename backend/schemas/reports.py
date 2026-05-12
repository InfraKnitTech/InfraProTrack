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


class EmployeeProductivityReportRow(BaseModel):
    group_by: str
    group_id: int | None
    group_name: str
    employee_id: int
    employee_name: str
    username: str
    login_time: datetime | None
    logout_time: datetime | None
    active_seconds: int
    productive_seconds: int
    idle_seconds: int


class EmployeeProductivityReportResponse(BaseModel):
    group_by: str
    start_date: str | None
    end_date: str | None
    rows: list[EmployeeProductivityReportRow]


class IdleTimeReportRow(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    username: str
    project_name: str | None
    manager_name: str | None
    shift_name: str | None
    start_time: datetime
    end_time: datetime | None
    duration: int
    reason_category: str | None
    reason: str | None


class IdleTimeReportResponse(BaseModel):
    start_date: str | None
    end_date: str | None
    rows: list[IdleTimeReportRow]
