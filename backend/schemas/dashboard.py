from pydantic import BaseModel
from typing import List


class MetricCard(BaseModel):
    total_productive: str
    total_idle: str
    total_unproductive: str
    active_employees: int
    total_employees: int


class ChartPoint(BaseModel):
    name: str
    productive: float
    unproductive: float


class AppUsagePoint(BaseModel):
    name: str
    value: int   # seconds


class DashboardResponse(BaseModel):
    metrics: MetricCard
    productivity_data: List[ChartPoint]
    app_usage_data: List[AppUsagePoint]
    top_domains: List[AppUsagePoint]
