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

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def create_all_tables():
    """
    Called on startup. Creates all tables if they do not exist.
    Safe to call multiple times.
    """
    import models  # noqa: F401 - imports all models so Base knows about them

    Base.metadata.create_all(bind=engine)
    _ensure_group_columns()
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
    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
