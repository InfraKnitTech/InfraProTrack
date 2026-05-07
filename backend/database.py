import os

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
    print("Database tables verified / created.")
