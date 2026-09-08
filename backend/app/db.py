from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def init_db():
    from app import models  # noqa: F401 -- ensure models are registered before create_all
    Base.metadata.create_all(bind=engine)
    _add_missing_columns()


def _add_missing_columns():
    """create_all() creates new tables but never adds a column to an existing
    one. For the handful of columns added after the first release, ALTER the
    table in place so an existing vidyutiq.db keeps working without a manual
    migration or a wipe."""
    wanted = {
        "chat_messages": {"actions_json": "TEXT"},
    }
    with engine.begin() as conn:
        for table, columns in wanted.items():
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            for name, ddl_type in columns.items():
                if name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl_type}")
