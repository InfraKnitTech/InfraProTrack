from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False)
    full_name = Column(String(150), nullable=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    role = Column(Enum("admin", "manager", "employee"), default="employee", nullable=False)
    employee_code = Column(String(64), unique=True, nullable=True)
    department = Column(String(120), nullable=True)
    phone = Column(String(40), nullable=True)
    location = Column(String(160), nullable=True)
    designation = Column(String(160), nullable=True)
    employment_status = Column(String(40), default="working", nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    timezone = Column(String(64), default="Asia/Kolkata")
    is_active = Column(Boolean, default=True, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # FK relationships
    shift_id = Column(Integer, ForeignKey("shifts.id"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    shift = relationship("Shift", back_populates="users")
    project = relationship("Project", back_populates="members", foreign_keys=[project_id])
    manager = relationship("User", remote_side=[id], foreign_keys=[manager_id])
    created_by = relationship("User", remote_side=[id], foreign_keys=[created_by_id])
    manager_profile = relationship("Manager", back_populates="user", uselist=False, cascade="all, delete-orphan")
    activity_logs = relationship("ActivityLog", back_populates="user", cascade="all, delete-orphan")
    app_usages = relationship("AppUsage", back_populates="user", cascade="all, delete-orphan")
    url_usages = relationship("UrlUsage", back_populates="user", cascade="all, delete-orphan")
    idle_logs = relationship("IdleLog", back_populates="user", cascade="all, delete-orphan")
    screenshots = relationship("Screenshot", back_populates="user", cascade="all, delete-orphan")
    productivity_scores = relationship("ProductivityScore", back_populates="user", cascade="all, delete-orphan")
    assets = relationship("EmployeeAsset", back_populates="user", cascade="all, delete-orphan")
    shift_assignments = relationship("EmployeeShiftAssignment", back_populates="user", cascade="all, delete-orphan")
    history = relationship("EmployeeHistory", back_populates="user", cascade="all, delete-orphan", foreign_keys="EmployeeHistory.user_id")
