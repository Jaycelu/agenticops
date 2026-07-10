"""Database engine, sessions, and migration readiness checks."""
from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection
from sqlalchemy.orm import declarative_base, sessionmaker

from config.settings import settings


BACKEND_ROOT = Path(__file__).resolve().parent


def _ensure_postgres(url: str) -> str:
    db_url = (url or "").strip()
    if not db_url.startswith("postgresql://") and not db_url.startswith("postgresql+psycopg2://"):
        raise RuntimeError(f"Unsupported database url: {db_url}. Only PostgreSQL is allowed.")
    return db_url


db_url = _ensure_postgres(settings.automation_database_url or settings.database_url)
engine = create_engine(
    db_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.debug,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))
    return config


def expected_database_revisions() -> set[str]:
    script = ScriptDirectory.from_config(get_alembic_config())
    return set(script.get_heads())


def current_database_revisions(connection: Connection | None = None) -> set[str]:
    if connection is not None:
        return set(MigrationContext.configure(connection).get_current_heads())
    with engine.connect() as managed_connection:
        return set(MigrationContext.configure(managed_connection).get_current_heads())


def verify_database_ready() -> None:
    expected = expected_database_revisions()
    current = current_database_revisions()
    if current != expected:
        current_label = ", ".join(sorted(current)) if current else "unversioned"
        expected_label = ", ".join(sorted(expected)) if expected else "no migration head"
        raise RuntimeError(
            "Database schema is not ready: "
            f"current={current_label}, expected={expected_label}. "
            "Run 'alembic upgrade head' before starting the application."
        )


def init_db() -> None:
    """Backward-compatible startup hook that now validates, never mutates, schema."""
    verify_database_ready()
