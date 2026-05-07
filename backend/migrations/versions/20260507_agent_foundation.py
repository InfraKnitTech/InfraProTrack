"""agent_foundation

Revision ID: 20260507_agent
Revises: 20260506_phase2
Create Date: 2026-05-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260507_agent"
down_revision: Union[str, Sequence[str], None] = "20260506_phase2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("os_type", sa.String(length=50), nullable=False),
        sa.Column("os_version", sa.String(length=255), nullable=True),
        sa.Column("agent_version", sa.String(length=50), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("token_id", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("security_key_hash", sa.String(length=128), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("registered_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id"),
        sa.UniqueConstraint("token_id"),
    )
    op.create_index(op.f("ix_agent_devices_device_id"), "agent_devices", ["device_id"], unique=False)
    op.create_index(op.f("ix_agent_devices_hostname"), "agent_devices", ["hostname"], unique=False)
    op.create_index(op.f("ix_agent_devices_id"), "agent_devices", ["id"], unique=False)
    op.create_index(op.f("ix_agent_devices_status"), "agent_devices", ["status"], unique=False)
    op.create_index(op.f("ix_agent_devices_token_id"), "agent_devices", ["token_id"], unique=False)

    op.create_table(
        "agent_registration_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("os_type", sa.String(length=50), nullable=False),
        sa.Column("os_version", sa.String(length=255), nullable=True),
        sa.Column("agent_version", sa.String(length=50), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=True),
        sa.Column("issued_token_id", sa.String(length=64), nullable=True),
        sa.Column("issued_token", sa.String(length=255), nullable=True),
        sa.Column("issued_security_key", sa.String(length=255), nullable=True),
        sa.Column("credentials_delivered_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agent_devices.id"]),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index(op.f("ix_agent_registration_requests_device_id"), "agent_registration_requests", ["device_id"], unique=False)
    op.create_index(op.f("ix_agent_registration_requests_id"), "agent_registration_requests", ["id"], unique=False)
    op.create_index(op.f("ix_agent_registration_requests_request_id"), "agent_registration_requests", ["request_id"], unique=False)
    op.create_index(op.f("ix_agent_registration_requests_status"), "agent_registration_requests", ["status"], unique=False)

    op.create_table(
        "agent_heartbeats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agent_devices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_heartbeats_agent_id"), "agent_heartbeats", ["agent_id"], unique=False)
    op.create_index(op.f("ix_agent_heartbeats_id"), "agent_heartbeats", ["id"], unique=False)

    op.create_table(
        "raw_agent_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("normalized", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agent_devices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_raw_agent_events_event_id"),
    )
    op.create_index(op.f("ix_raw_agent_events_agent_id"), "raw_agent_events", ["agent_id"], unique=False)
    op.create_index(op.f("ix_raw_agent_events_captured_at"), "raw_agent_events", ["captured_at"], unique=False)
    op.create_index(op.f("ix_raw_agent_events_event_id"), "raw_agent_events", ["event_id"], unique=False)
    op.create_index(op.f("ix_raw_agent_events_event_type"), "raw_agent_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_raw_agent_events_id"), "raw_agent_events", ["id"], unique=False)

    op.create_table(
        "file_usages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("app_name", sa.String(length=255), nullable=True),
        sa.Column("window_title", sa.String(length=500), nullable=True),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agent_devices.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_file_usages_agent_id"), "file_usages", ["agent_id"], unique=False)
    op.create_index(op.f("ix_file_usages_id"), "file_usages", ["id"], unique=False)
    op.create_index(op.f("ix_file_usages_user_id"), "file_usages", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_file_usages_user_id"), table_name="file_usages")
    op.drop_index(op.f("ix_file_usages_id"), table_name="file_usages")
    op.drop_index(op.f("ix_file_usages_agent_id"), table_name="file_usages")
    op.drop_table("file_usages")
    op.drop_index(op.f("ix_raw_agent_events_id"), table_name="raw_agent_events")
    op.drop_index(op.f("ix_raw_agent_events_event_type"), table_name="raw_agent_events")
    op.drop_index(op.f("ix_raw_agent_events_event_id"), table_name="raw_agent_events")
    op.drop_index(op.f("ix_raw_agent_events_captured_at"), table_name="raw_agent_events")
    op.drop_index(op.f("ix_raw_agent_events_agent_id"), table_name="raw_agent_events")
    op.drop_table("raw_agent_events")
    op.drop_index(op.f("ix_agent_heartbeats_id"), table_name="agent_heartbeats")
    op.drop_index(op.f("ix_agent_heartbeats_agent_id"), table_name="agent_heartbeats")
    op.drop_table("agent_heartbeats")
    op.drop_index(op.f("ix_agent_registration_requests_status"), table_name="agent_registration_requests")
    op.drop_index(op.f("ix_agent_registration_requests_request_id"), table_name="agent_registration_requests")
    op.drop_index(op.f("ix_agent_registration_requests_id"), table_name="agent_registration_requests")
    op.drop_index(op.f("ix_agent_registration_requests_device_id"), table_name="agent_registration_requests")
    op.drop_table("agent_registration_requests")
    op.drop_index(op.f("ix_agent_devices_token_id"), table_name="agent_devices")
    op.drop_index(op.f("ix_agent_devices_status"), table_name="agent_devices")
    op.drop_index(op.f("ix_agent_devices_id"), table_name="agent_devices")
    op.drop_index(op.f("ix_agent_devices_hostname"), table_name="agent_devices")
    op.drop_index(op.f("ix_agent_devices_device_id"), table_name="agent_devices")
    op.drop_table("agent_devices")
