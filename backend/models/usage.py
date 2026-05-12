from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from core.time_utils import now_ist
from database import Base


class AppUsage(Base):
    __tablename__ = "app_usages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    app_name = Column(String(255), nullable=False)
    category = Column(Enum("productive", "unproductive", "prohibited", "neutral"), default="neutral")
    duration = Column(Integer, default=0)  # seconds
    date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime, default=now_ist)

    user = relationship("User", back_populates="app_usages")


class UrlUsage(Base):
    __tablename__ = "url_usages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    domain = Column(String(500), nullable=False)
    url = Column(String(2000), nullable=True)
    category = Column(Enum("productive", "unproductive", "prohibited", "neutral"), default="neutral")
    duration = Column(Integer, default=0)  # seconds
    date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime, default=now_ist)

    user = relationship("User", back_populates="url_usages")


class BrowserUrlActivity(Base):
    __tablename__ = "browser_url_activities"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    app_name = Column(String(255), nullable=True)
    process_name = Column(String(255), nullable=True)
    window_title = Column(String(500), nullable=True)
    domain = Column(String(500), nullable=False, index=True)
    url = Column(String(2000), nullable=False)
    category = Column(Enum("productive", "unproductive", "prohibited", "neutral"), default="neutral")
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    duration = Column(Integer, default=0)
    created_at = Column(DateTime, default=now_ist)

    user = relationship("User")
