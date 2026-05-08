from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class EmployeeAsset(Base):
    __tablename__ = "employee_assets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    asset_type = Column(String(80), nullable=True)
    asset_name = Column(String(160), nullable=False)
    asset_tag = Column(String(120), nullable=True)
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="assets")


class EmployeeHistory(Base):
    __tablename__ = "employee_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    change_type = Column(String(80), nullable=False)
    field_name = Column(String(120), nullable=True)
    old_value = Column(String(1000), nullable=True)
    new_value = Column(String(1000), nullable=True)
    changed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id], back_populates="history")
    changed_by = relationship("User", foreign_keys=[changed_by_id])
