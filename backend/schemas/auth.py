from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional


class RegisterRequest(BaseModel):
    username: str
    full_name: Optional[str] = None
    email: EmailStr
    password: str
    role: Optional[str] = "employee"
    employee_code: Optional[str] = None
    department: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    user: dict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: str
