from datetime import datetime

from pydantic import BaseModel, Field


class RuleBase(BaseModel):
    app_name: str | None = Field(default=None, max_length=255)
    domain: str | None = Field(default=None, max_length=500)
    category: str = Field(default="neutral", pattern="^(productive|unproductive|prohibited|neutral)$")
    severity: str = Field(default="medium", pattern="^(low|medium|high)$")
    project_id: int | None = None


class RuleCreate(RuleBase):
    pass


class RuleUpdate(BaseModel):
    app_name: str | None = Field(default=None, max_length=255)
    domain: str | None = Field(default=None, max_length=500)
    category: str | None = Field(default=None, pattern="^(productive|unproductive|prohibited|neutral)$")
    severity: str | None = Field(default=None, pattern="^(low|medium|high)$")
    project_id: int | None = None


class RuleResponse(RuleBase):
    id: int
    project_name: str | None = None
    created_by: int | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class RuleListResponse(BaseModel):
    items: list[RuleResponse]
