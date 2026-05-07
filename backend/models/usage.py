from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class AppUsage(Base):
    __tablename__ = "app_usages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    app_name = Column(String(255), nullable=False)
    category = Column(Enum("productive", "unproductive", "prohibited", "neutral"), default="neutral")
    duration = Column(Integer, default=0)  # seconds
    date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="url_usages")
