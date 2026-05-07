from pydantic import BaseModel


class AnalyticsPoint(BaseModel):
    name: str
    value: int
    category: str | None = None


class AnalyticsListResponse(BaseModel):
    start_date: str | None
    end_date: str | None
    items: list[AnalyticsPoint]
