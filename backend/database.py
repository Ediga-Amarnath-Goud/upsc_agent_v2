import os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)
(DATA_DIR / "uploads").mkdir(exist_ok=True)
(DATA_DIR / "markdown").mkdir(exist_ok=True)
(DATA_DIR / "pdfs").mkdir(exist_ok=True)
(DATA_DIR / "ca_images").mkdir(exist_ok=True)
(DATA_DIR / "diagnostic").mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR / 'upsc_agent.db'}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ── Current Affairs Database ────────────────────────────────────────────────

CA_DB_URL = f"sqlite:///{DATA_DIR / 'current_affairs.db'}"

ca_engine = create_engine(
    CA_DB_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)


@event.listens_for(ca_engine, "connect")
def set_ca_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


SessionLocalCA = sessionmaker(autocommit=False, autoflush=False, bind=ca_engine)
CABase = declarative_base()


def get_ca_session():
    session = SessionLocalCA()
    try:
        yield session
    finally:
        session.close()


# ── Migration ────────────────────────────────────────────────────────────────

def _ensure_columns():
    """Add new columns to existing tables (SQLite ALTER TABLE migration)."""
    from sqlalchemy import inspect, text

    main_cols_map = {
        "student_profile": [
            ("diagnostic_completed", "BOOLEAN DEFAULT 0"),
            ("last_diagnostic_at", "DATETIME"),
            ("per_subject_accuracy", "JSON DEFAULT '{}'"),
        ],
        "diagnostic_questions": [
            ("ca_sub_topic", "VARCHAR"),
            ("question_type", "VARCHAR"),
        ],
    }
    with engine.begin() as conn:
        inspector = inspect(engine)
        for table, columns in main_cols_map.items():
            existing = {c["name"] for c in inspector.get_columns(table)}
            for col_name, col_type in columns:
                if col_name not in existing:
                    conn.execute(text(
                        f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"
                    ))


# ── Init ────────────────────────────────────────────────────────────────────

def _ensure_ca_columns():
    """Add new columns to existing CA table (SQLite ALTER TABLE migration)."""
    from sqlalchemy import inspect, text

    ca_cols_map = {
        "current_affairs": [
            ("subject", "VARCHAR"),
            ("historical_context", "TEXT"),
            ("image_url", "VARCHAR"),
            ("image_path", "VARCHAR"),
        ],
        "curated_ca": [
            ("images", "JSON DEFAULT '[]'"),
        ],
    }
    with ca_engine.begin() as conn:
        inspector = inspect(ca_engine)
        for table, columns in ca_cols_map.items():
            existing = {c["name"] for c in inspector.get_columns(table)}
            for col_name, col_type in columns:
                if col_name not in existing:
                    conn.execute(text(
                        f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"
                    ))


def init_db():
    from models import Base as ModelsBase
    from models import CABase as ModelsCABase
    ModelsBase.metadata.create_all(bind=engine)
    ModelsCABase.metadata.create_all(bind=ca_engine)
    _ensure_columns()
    _ensure_ca_columns()
