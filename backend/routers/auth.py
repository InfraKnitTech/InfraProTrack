from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.deps import get_db
from core.security import create_access_token, get_password_hash, verify_password
from core.time_utils import now_ist
from models.user import User
from schemas.auth import LoginRequest, RegisterRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", status_code=201, summary="Register a new user")
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    user = User(
        username=body.username,
        full_name=body.full_name,
        email=body.email,
        password=get_password_hash(body.password),
        role=body.role or "employee",
        employee_code=body.employee_code,
        department=body.department,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "User registered successfully", "user_id": user.id}


@router.post("/login", response_model=TokenResponse, summary="Login with username and password")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password):
        raise HTTPException(status_code=400, detail="Invalid username or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")

    user.last_login_at = now_ist()
    db.commit()

    token = create_access_token({"id": user.id, "role": user.role})
    return TokenResponse(
        token=token,
        user={"id": user.id, "username": user.username, "role": user.role},
    )
