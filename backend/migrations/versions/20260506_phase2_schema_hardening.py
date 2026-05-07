"""phase2_schema_hardening

Revision ID: 20260506_phase2
Revises: f858b6a15ba7
Create Date: 2026-05-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260506_phase2"
down_revision: Union[str, Sequence[str], None] = "f858b6a15ba7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.String(length=150), nullable=True))
    op.add_column("users", sa.Column("employee_code", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("department", sa.String(length=120), nullable=True))
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(), nullable=True))
    op.create_unique_constraint("uq_users_employee_code", "users", ["employee_code"])

    op.create_table(
        "managers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("department", sa.String(length=120), nullable=True),
        sa.Column("region", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_managers_id"), "managers", ["id"], unique=False)
    op.create_index(op.f("ix_managers_user_id"), "managers", ["user_id"], unique=False)

    op.add_column("projects", sa.Column("client_name", sa.String(length=200), nullable=True))
    op.add_column("projects", sa.Column("status", sa.String(length=40), nullable=False, server_default="active"))

    op.add_column("shifts", sa.Column("grace_minutes", sa.Integer(), nullable=False, server_default="10"))
    op.add_column("shifts", sa.Column("is_overnight", sa.Integer(), nullable=False, server_default="0"))

    op.add_column("activity_logs", sa.Column("file_path", sa.String(length=1000), nullable=True))
    op.alter_column(
        "activity_logs",
        "type",
        existing_type=sa.Enum("active", "idle", "unproductive"),
        type_=sa.Enum("login", "logout", "active", "idle", "unproductive"),
        existing_nullable=False,
    )
    op.create_index("ix_activity_logs_user_start", "activity_logs", ["user_id", "start_time"], unique=False)
    op.create_index("ix_activity_logs_type_start", "activity_logs", ["type", "start_time"], unique=False)

    op.add_column("screenshots", sa.Column("storage_key", sa.String(length=500), nullable=True))
    op.add_column("screenshots", sa.Column("productivity_score", sa.Integer(), nullable=True))

    op.add_column("app_rules", sa.Column("severity", sa.String(length=20), nullable=False, server_default="medium"))
    op.add_column("app_rules", sa.Column("project_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_app_rules_project_id_projects", "app_rules", "projects", ["project_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_app_rules_project_id_projects", "app_rules", type_="foreignkey")
    op.drop_column("app_rules", "project_id")
    op.drop_column("app_rules", "severity")

    op.drop_column("screenshots", "productivity_score")
    op.drop_column("screenshots", "storage_key")

    op.drop_index("ix_activity_logs_type_start", table_name="activity_logs")
    op.drop_index("ix_activity_logs_user_start", table_name="activity_logs")
    op.alter_column(
        "activity_logs",
        "type",
        existing_type=sa.Enum("login", "logout", "active", "idle", "unproductive"),
        type_=sa.Enum("active", "idle", "unproductive"),
        existing_nullable=False,
    )
    op.drop_column("activity_logs", "file_path")

    op.drop_column("shifts", "is_overnight")
    op.drop_column("shifts", "grace_minutes")

    op.drop_column("projects", "status")
    op.drop_column("projects", "client_name")

    op.drop_index(op.f("ix_managers_user_id"), table_name="managers")
    op.drop_index(op.f("ix_managers_id"), table_name="managers")
    op.drop_table("managers")

    op.drop_constraint("uq_users_employee_code", "users", type_="unique")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "is_active")
    op.drop_column("users", "department")
    op.drop_column("users", "employee_code")
    op.drop_column("users", "full_name")
