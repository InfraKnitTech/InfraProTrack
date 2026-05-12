from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from core.time_utils import now_ist
from database import Base


class CustomGroup(Base):
    __tablename__ = "custom_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False)
    category_name = Column(String(120), nullable=False, index=True)
    description = Column(Text, nullable=True)
    parent_group_id = Column(Integer, ForeignKey("custom_groups.id"), nullable=True, index=True)
    leader_user_id = Column(Integer, nullable=True, index=True)
    leader_title = Column(String(160), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=now_ist)

    parent_group = relationship(
        "CustomGroup",
        remote_side=[id],
        back_populates="child_groups",
        foreign_keys=[parent_group_id],
    )
    child_groups = relationship(
        "CustomGroup",
        back_populates="parent_group",
        cascade="all, delete-orphan",
        single_parent=True,
    )
    members = relationship(
        "CustomGroupMember",
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="CustomGroupMember.sort_order.asc()",
    )


class CustomGroupMember(Base):
    __tablename__ = "custom_group_members"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("custom_groups.id"), nullable=False, index=True)
    parent_member_id = Column(Integer, ForeignKey("custom_group_members.id"), nullable=True, index=True)
    member_type = Column(String(32), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    manager_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    department_name = Column(String(120), nullable=True, index=True)
    label_override = Column(String(160), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=now_ist)

    group = relationship("CustomGroup", back_populates="members")
    parent = relationship("CustomGroupMember", remote_side=[id], back_populates="children")
    children = relationship("CustomGroupMember", back_populates="parent", cascade="all, delete-orphan")
    user = relationship("User", foreign_keys=[user_id])
    manager_user = relationship("User", foreign_keys=[manager_user_id])
    project = relationship("Project", foreign_keys=[project_id])
