from pydantic import BaseModel
from datetime import datetime


class AnalyticsPoint(BaseModel):
    name: str
    value: int
    category: str | None = None


class AnalyticsListResponse(BaseModel):
    start_date: str | None
    end_date: str | None
    items: list[AnalyticsPoint]


class AppUsageScopeRow(BaseModel):
    group_by: str
    group_id: int | None
    group_name: str
    total_seconds: int
    top_app_name: str | None
    top_app_seconds: int
    distinct_app_count: int


class AppUsageScopeResponse(BaseModel):
    group_by: str
    start_date: str | None
    end_date: str | None
    items: list[AppUsageScopeRow]


class SessionEventRow(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    username: str
    event_type: str
    captured_at: datetime | None
    department: str | None = None
    project_name: str | None = None


class SessionEventResponse(BaseModel):
    items: list[SessionEventRow]


class ActivityDetailRow(BaseModel):
    id: int
    source: str
    employee_id: int
    employee_name: str
    username: str
    manager_name: str | None = None
    department: str | None = None
    project_name: str | None = None
    application: str | None = None
    browser: str | None = None
    domain: str | None = None
    url: str | None = None
    window_title: str | None = None
    category: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration: int


class ActivityDetailResponse(BaseModel):
    items: list[ActivityDetailRow]


class ActivityRollupRow(BaseModel):
    group_by: str
    group_id: int | None = None
    group_name: str
    productive_seconds: int
    unproductive_seconds: int
    idle_seconds: int
    total_seconds: int
    productivity_percent: float


class ActivityRollupResponse(BaseModel):
    group_by: str
    source: str
    items: list[ActivityRollupRow]
