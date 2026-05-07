from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


class AgentDevice(Base):
    __tablename__ = "agent_devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(128), nullable=False, unique=True, index=True)
    hostname = Column(String(255), nullable=False, index=True)
    os_type = Column(String(50), nullable=False)
    os_version = Column(String(255), nullable=True)
    agent_version = Column(String(50), nullable=True)
    username = Column(String(255), nullable=True)
    ip_address = Column(String(64), nullable=True)
    status = Column(String(30), default="active", nullable=False, index=True)
    token_id = Column(String(64), nullable=False, unique=True, index=True)
    token_hash = Column(String(128), nullable=False)
    security_key_hash = Column(String(128), nullable=False)
    last_seen_at = Column(DateTime, nullable=True)
    registered_at = Column(DateTime, default=datetime.utcnow)
    revoked_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    heartbeats = relationship("AgentHeartbeat", back_populates="agent", cascade="all, delete-orphan")
    events = relationship("RawAgentEvent", back_populates="agent", cascade="all, delete-orphan")


class AgentRegistrationRequest(Base):
    __tablename__ = "agent_registration_requests"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String(64), nullable=False, unique=True, index=True)
    device_id = Column(String(128), nullable=False, index=True)
    hostname = Column(String(255), nullable=False)
    os_type = Column(String(50), nullable=False)
    os_version = Column(String(255), nullable=True)
    agent_version = Column(String(50), nullable=True)
    username = Column(String(255), nullable=True)
    ip_address = Column(String(64), nullable=True)
    status = Column(String(30), default="pending", nullable=False, index=True)
    agent_id = Column(Integer, ForeignKey("agent_devices.id"), nullable=True)
    issued_token_id = Column(String(64), nullable=True)
    issued_token = Column(String(255), nullable=True)
    issued_security_key = Column(String(255), nullable=True)
    credentials_delivered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    decided_at = Column(DateTime, nullable=True)
    decided_by = Column(Integer, ForeignKey("users.id"), nullable=True)


class AgentHeartbeat(Base):
    __tablename__ = "agent_heartbeats"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agent_devices.id"), nullable=False, index=True)
    status = Column(String(30), default="online", nullable=False)
    captured_at = Column(DateTime, nullable=True)
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    payload = Column(Text, nullable=True)

    agent = relationship("AgentDevice", back_populates="heartbeats")


class RawAgentEvent(Base):
    __tablename__ = "raw_agent_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_raw_agent_events_event_id"),)

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(100), nullable=False, index=True)
    agent_id = Column(Integer, ForeignKey("agent_devices.id"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    captured_at = Column(DateTime, nullable=True, index=True)
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    payload = Column(Text, nullable=False)
    normalized = Column(Boolean, default=False, nullable=False)

    agent = relationship("AgentDevice", back_populates="events")


class FileUsage(Base):
    __tablename__ = "file_usages"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agent_devices.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    file_path = Column(String(1000), nullable=False)
    app_name = Column(String(255), nullable=True)
    window_title = Column(String(500), nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    duration = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
