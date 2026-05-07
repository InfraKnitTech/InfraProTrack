from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(Enum("login", "logout", "active", "idle", "unproductive"), nullable=False)
    app_name = Column(String(255), nullable=True)
    window_title = Column(String(500), nullable=True)
    url = Column(String(2000), nullable=True)
    file_path = Column(String(1000), nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    duration = Column(Integer, default=0)  # seconds
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="activity_logs")


Index("ix_activity_logs_user_start", ActivityLog.user_id, ActivityLog.start_time)
Index("ix_activity_logs_type_start", ActivityLog.type, ActivityLog.start_time)
