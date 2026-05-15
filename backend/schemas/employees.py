from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class EmployeeAssetIn(BaseModel):
    asset_type: str | None = Field(default=None, max_length=80)
    asset_name: str = Field(min_length=1, max_length=160)
    asset_tag: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=500)


class EmployeeAssetOut(EmployeeAssetIn):
    id: int

    class Config:
        from_attributes = True


class EmployeeScheduleIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    shift_id: int


class EmployeeScheduleOut(BaseModel):
    id: int
    weekday: int
    shift_id: int
    shift_name: str
    start_time: str
    end_time: str
    timezone: str


class EmployeeBase(BaseModel):
    username: str = Field(min_length=2, max_length=100)
    full_name: str = Field(min_length=1, max_length=150)
    email: EmailStr
    employee_code: str | None = Field(default=None, max_length=64)
    department: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    location: str | None = Field(default=None, max_length=160)
    designation: str | None = Field(default=None, max_length=160)
    employment_status: str = Field(default="working", pattern="^(working|retired|left|inactive)$")
    manager_id: int | None = None
    project_id: int | None = None
    shift_id: int | None = None


class EmployeeCreate(EmployeeBase):
    agent_id: int | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)
    assets: list[EmployeeAssetIn] = Field(default_factory=list)
    schedule: list[EmployeeScheduleIn] = Field(default_factory=list)


class EmployeeUpdate(EmployeeBase):
    password: str | None = Field(default=None, min_length=6, max_length=128)
    assets: list[EmployeeAssetIn] = Field(default_factory=list)
    schedule: list[EmployeeScheduleIn] = Field(default_factory=list)


class EmployeeOut(EmployeeBase):
    id: int
    role: str
    is_active: bool
    created_at: datetime
    created_by_id: int | None
    created_by_name: str | None
    manager_name: str | None
    project_name: str | None
    shift_name: str | None
    assets: list[EmployeeAssetOut]
    schedule: list[EmployeeScheduleOut]


class EmployeeListResponse(BaseModel):
    items: list[EmployeeOut]


class PendingEmployeeAgentOut(BaseModel):
    agent_id: int
    device_id: str
    hostname: str
    username: str | None
    os_type: str
    os_version: str | None
    agent_version: str | None
    ip_address: str | None
    status: str
    last_seen_at: datetime | None
    registered_at: datetime | None
    suggested_full_name: str
    suggested_username: str
    suggested_email: str
    suggested_employee_code: str


class PendingEmployeeAgentListResponse(BaseModel):
    items: list[PendingEmployeeAgentOut]


class EmployeeInsightEvent(BaseModel):
    id: int
    type: str
    app_name: str | None
    window_title: str | None
    url: str | None = None
    domain: str | None = None
    start_time: datetime | None
    end_time: datetime | None
    duration: int


class EmployeeHistoryOut(BaseModel):
    id: int
    change_type: str
    field_name: str | None
    old_value: str | None
    new_value: str | None
    changed_by_id: int | None
    changed_by_name: str | None
    created_at: datetime


class EmployeeInsightResponse(BaseModel):
    employee: EmployeeOut
    productive_seconds: int
    unproductive_seconds: int
    idle_seconds: int
    total_tracked_seconds: int
    productivity_percent: float
    top_apps: list[dict]
    recent_activity: list[EmployeeInsightEvent]
    history: list[EmployeeHistoryOut]


class EmployeeHistoryResponse(BaseModel):
    items: list[EmployeeHistoryOut]
