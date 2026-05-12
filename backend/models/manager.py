from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from core.time_utils import now_ist
from database import Base


class Manager(Base):
    __tablename__ = "managers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    department = Column(String(120), nullable=True)
    region = Column(String(120), nullable=True)
    created_at = Column(DateTime, default=now_ist)

    user = relationship("User", back_populates="manager_profile")
