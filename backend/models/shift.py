from sqlalchemy import Column, Integer, String, Time, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from core.time_utils import now_ist
from database import Base


class Shift(Base):
    __tablename__ = "shifts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    timezone = Column(String(64), default="Asia/Kolkata")
    grace_minutes = Column(Integer, default=10, nullable=False)
    is_overnight = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=now_ist)

    users = relationship("User", back_populates="shift")


class EmployeeShiftAssignment(Base):
    __tablename__ = "employee_shift_assignments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    weekday = Column(Integer, nullable=False, index=True)  # Monday=0, Sunday=6
    shift_id = Column(Integer, ForeignKey("shifts.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=now_ist)

    user = relationship("User", back_populates="shift_assignments")
    shift = relationship("Shift")
