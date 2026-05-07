from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class IdleLog(Base):
    __tablename__ = "idle_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    start_time = Column(DateTime, nullable=False)
    duration = Column(Integer, default=0)  # seconds
    reason = Column(Text, nullable=True)  # employee-provided reason
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="idle_logs")


class Screenshot(Base):
    __tablename__ = "screenshots"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    file_path = Column(String(500), nullable=False)   # path on server / S3 key
    storage_key = Column(String(500), nullable=True)
    productivity_score = Column(Integer, nullable=True)
    trigger_reason = Column(String(255), nullable=True)  # e.g. "low_productivity", "random"
    activity_log_id = Column(Integer, ForeignKey("activity_logs.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="screenshots")


class ProductivityScore(Base):
    __tablename__ = "productivity_scores"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    score = Column(Integer, default=0)          # 0–100
    productive_pct = Column(Integer, default=0) # percentage
    idle_pct = Column(Integer, default=0)
    unproductive_pct = Column(Integer, default=0)
    login_time = Column(DateTime, nullable=True)
    logout_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="productivity_scores")


class AppRule(Base):
    __tablename__ = "app_rules"

    id = Column(Integer, primary_key=True, index=True)
    app_name = Column(String(255), nullable=True)   # match by app name
    domain = Column(String(500), nullable=True)     # match by domain
    category = Column(
        String(20),
        nullable=False,
        default="neutral"
    )  # productive / unproductive / prohibited / neutral
    severity = Column(String(20), default="medium", nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
