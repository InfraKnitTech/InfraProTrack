from datetime import datetime

from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    client_name: str | None = Field(default=None, max_length=200)
    status: str = Field(default="active", pattern="^(active|paused|completed|archived)$")
    manager_id: int | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    client_name: str | None = Field(default=None, max_length=200)
    status: str | None = Field(default=None, pattern="^(active|paused|completed|archived)$")
    manager_id: int | None = None


class ProjectTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    assignee_type: str = Field(pattern="^(group|manager|employee)$")
    group_id: int | None = None
    manager_user_id: int | None = None
    employee_user_id: int | None = None
    due_at: datetime | None = None
    status: str = Field(default="todo", pattern="^(todo|in_progress|completed|blocked)$")


class ProjectTaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    assignee_type: str | None = Field(default=None, pattern="^(group|manager|employee)$")
    group_id: int | None = None
    manager_user_id: int | None = None
    employee_user_id: int | None = None
    due_at: datetime | None = None
    status: str | None = Field(default=None, pattern="^(todo|in_progress|completed|blocked)$")


class ProjectTaskResponse(BaseModel):
    id: int
    project_id: int
    title: str
    description: str | None
    assignee_type: str
    assignee_label: str
    group_id: int | None
    manager_user_id: int | None
    employee_user_id: int | None
    due_at: datetime | None
    status: str
    created_by: int | None
    created_at: datetime


class ProjectSummaryResponse(BaseModel):
    employee_count: int
    task_count: int
    open_task_count: int
    productive_seconds: int
    unproductive_seconds: int
    active_seconds: int
    idle_seconds: int
    total_tracked_seconds: int
    productivity_percent: float


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str | None
    client_name: str | None
    status: str
    manager_id: int | None
    manager_name: str | None
    created_at: datetime
    summary: ProjectSummaryResponse


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]


class ProjectDashboardRow(BaseModel):
    id: int | None
    name: str
    employee_count: int
    productive_seconds: int
    unproductive_seconds: int
    active_seconds: int
    idle_seconds: int
    total_tracked_seconds: int
    productivity_percent: float


class ProjectDashboardResponse(BaseModel):
    project: ProjectResponse
    tasks: list[ProjectTaskResponse]
    manager_rows: list[ProjectDashboardRow]
    employee_rows: list[ProjectDashboardRow]
