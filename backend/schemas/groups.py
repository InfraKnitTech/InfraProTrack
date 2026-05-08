from datetime import datetime

from pydantic import BaseModel, Field


class GroupMemberCreate(BaseModel):
    client_key: str = Field(min_length=1, max_length=64)
    parent_client_key: str | None = Field(default=None, max_length=64)
    member_type: str = Field(pattern="^(user|manager|project|department)$")
    user_id: int | None = None
    manager_user_id: int | None = None
    project_id: int | None = None
    department_name: str | None = Field(default=None, max_length=120)
    label_override: str | None = Field(default=None, max_length=160)
    sort_order: int = 0


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    category_name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    parent_group_id: int | None = None
    leader_user_id: int | None = None
    leader_title: str | None = Field(default=None, max_length=160)
    members: list[GroupMemberCreate]


class GroupUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    category_name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    parent_group_id: int | None = None
    leader_user_id: int | None = None
    leader_title: str | None = Field(default=None, max_length=160)
    members: list[GroupMemberCreate]


class GroupMemberResponse(BaseModel):
    id: int
    parent_member_id: int | None
    member_type: str
    user_id: int | None
    manager_user_id: int | None
    project_id: int | None
    department_name: str | None
    label_override: str | None
    display_label: str
    employee_count: int
    child_count: int


class GroupSummaryResponse(BaseModel):
    employee_count: int
    login_count: int
    logout_count: int
    productive_seconds: int
    unproductive_seconds: int
    active_seconds: int
    idle_seconds: int
    total_tracked_seconds: int
    productivity_percent: float


class GroupResponse(BaseModel):
    id: int
    name: str
    category_name: str
    description: str | None
    parent_group_id: int | None
    parent_group_name: str | None
    leader_user_id: int | None
    leader_name: str | None
    leader_title: str | None
    created_by: int | None
    created_at: datetime
    members: list[GroupMemberResponse]
    summary: GroupSummaryResponse


class GroupListResponse(BaseModel):
    items: list[GroupResponse]


class GroupOption(BaseModel):
    id: str
    label: str
    member_type: str
    ref_id: int | None = None
    department_name: str | None = None


class GroupOptionsResponse(BaseModel):
    users: list[GroupOption]
    managers: list[GroupOption]
    projects: list[GroupOption]
    departments: list[GroupOption]
