from sqlalchemy import Column, Integer, String, Time, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
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
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="shift")
