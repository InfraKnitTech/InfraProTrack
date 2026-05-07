from pydantic import BaseModel


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
