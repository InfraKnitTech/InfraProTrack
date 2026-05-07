from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AgentIdentity(BaseModel):
    device_id: str
    hostname: str
    os_type: str
    os_version: Optional[str] = None
    agent_version: Optional[str] = None
    username: Optional[str] = None


class AgentRegisterRequest(AgentIdentity):
    master_password: Optional[str] = None


class AgentCredentials(BaseModel):
    agent_id: int
    agent_token_id: str
    agent_token: str
    security_key: str


class AgentRegisterResponse(BaseModel):
    status: str
    request_id: Optional[str] = None
    credentials: Optional[AgentCredentials] = None
    message: str


class AgentRegistrationStatusResponse(BaseModel):
    status: str
    credentials: Optional[AgentCredentials] = None
    message: str


class AgentHeartbeatIn(BaseModel):
    status: str = "online"
    captured_at: Optional[datetime] = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentEventIn(BaseModel):
    event_id: str
    event_type: str
    captured_at: Optional[datetime] = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentEventBatchIn(BaseModel):
    events: list[AgentEventIn]


class AgentEventBatchOut(BaseModel):
    accepted: int
    duplicates: int
    normalized: int = 0
    skipped: int = 0


class AgentNormalizationOut(BaseModel):
    normalized: int
    skipped: int


class AgentConfigOut(BaseModel):
    idle_threshold_seconds: int
    check_interval_seconds: int
    batch_interval_seconds: int
    screenshot_trigger_productivity_below: float


class PendingAgentOut(BaseModel):
    id: int
    request_id: str
    device_id: str
    hostname: str
    os_type: str
    os_version: Optional[str]
    agent_version: Optional[str]
    username: Optional[str]
    ip_address: Optional[str]
    status: str
    created_at: datetime
