import os

from sqlalchemy import inspect, text
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from core.config import mysql

# DATABASE_URL can override config.json for local/dev/prod deployments.
DATABASE_URL = os.getenv("DATABASE_URL", mysql.URL)

engine_kwargs = {
    "pool_pre_ping": True,
    "echo": False,
}

if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_size"] = mysql.POOL_MAX
    engine_kwargs["max_overflow"] = 5
    engine_kwargs["pool_recycle"] = 1200
    engine_kwargs["pool_timeout"] = 10
    engine_kwargs["connect_args"] = {
        "connect_timeout": 10,
        "read_timeout": 30,
        "write_timeout": 30,
    }

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def reset_connection_pool():
    """Drop pooled DB connections after a network-level DB failure."""
    engine.dispose()


def create_all_tables():
    """
    Called on startup. Creates all tables if they do not exist.
    Safe to call multiple times.
    """
    import models  # noqa: F401 - imports all models so Base knows about them

    Base.metadata.create_all(bind=engine)
    _ensure_group_columns()
    _ensure_employee_columns()
    _ensure_agent_columns()
    print("Database tables verified / created.")


def _ensure_group_columns():
    inspector = inspect(engine)
    if "custom_groups" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("custom_groups")}
    statements: list[str] = []
    if "leader_user_id" not in columns:
        statements.append("ALTER TABLE custom_groups ADD COLUMN leader_user_id INTEGER NULL")
    if "leader_title" not in columns:
        statements.append("ALTER TABLE custom_groups ADD COLUMN leader_title VARCHAR(160) NULL")
    if "parent_group_id" not in columns:
        statements.append("ALTER TABLE custom_groups ADD COLUMN parent_group_id INTEGER NULL")
    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _ensure_employee_columns():
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("users")}
    statements: list[str] = []
    additions = {
        "phone": "VARCHAR(40) NULL",
        "location": "VARCHAR(160) NULL",
        "designation": "VARCHAR(160) NULL",
        "employment_status": "VARCHAR(40) NOT NULL DEFAULT 'working'",
        "created_by_id": "INTEGER NULL",
        "is_monitoring_subject": "BOOLEAN NOT NULL DEFAULT FALSE",
    }
    for column_name, definition in additions.items():
        if column_name not in columns:
            statements.append(f"ALTER TABLE users ADD COLUMN {column_name} {definition}")
    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _ensure_agent_columns():
    inspector = inspect(engine)
    if "agent_devices" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("agent_devices")}
    if "user_id" in columns:
        return
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE agent_devices ADD COLUMN user_id INTEGER NULL"))
