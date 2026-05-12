from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from core.time_utils import now_ist
from database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    client_name = Column(String(200), nullable=True)
    status = Column(String(40), default="active", nullable=False)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=now_ist)

    members = relationship("User", back_populates="project", foreign_keys="User.project_id")
    manager = relationship("User", foreign_keys=[manager_id])
    tasks = relationship("ProjectTask", back_populates="project", cascade="all, delete-orphan")


class ProjectTask(Base):
    __tablename__ = "project_tasks"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    assignee_type = Column(String(30), nullable=False)
    group_id = Column(Integer, ForeignKey("custom_groups.id"), nullable=True)
    manager_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    employee_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    due_at = Column(DateTime, nullable=True)
    status = Column(String(40), default="todo", nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=now_ist)

    project = relationship("Project", back_populates="tasks")
    group = relationship("CustomGroup")
    manager_user = relationship("User", foreign_keys=[manager_user_id])
    employee_user = relationship("User", foreign_keys=[employee_user_id])
    creator = relationship("User", foreign_keys=[created_by])
