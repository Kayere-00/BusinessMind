"""Database engine and session management (SQLAlchemy 2.x).

PostgreSQL is the production database (docker-compose provisions it and passes
DATABASE_URL explicitly). When DATABASE_URL is NOT set and the built-in default
PostgreSQL endpoint is unreachable, the app falls back to a local SQLite file —
this only exists so the app boots in zero-config demo/preview environments.
"""
import logging
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

logger = logging.getLogger("businessmind.db")
settings = get_settings()


def _choose_url() -> str:
    url = settings.DATABASE_URL
    if "DATABASE_URL" in os.environ or url.startswith("sqlite"):
        return url
    # Default URL: probe PostgreSQL; fall back to SQLite for zero-config demos.
    try:
        import psycopg2

        conn = psycopg2.connect(url.replace("+psycopg2", ""), connect_timeout=3)
        conn.close()
        return url
    except Exception:
        fallback = Path(settings.STORAGE_DIR) / "businessmind.db"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        logger.warning(
            "PostgreSQL unreachable and DATABASE_URL not set — using SQLite at %s (demo mode).",
            fallback,
        )
        return f"sqlite:///{fallback}"


_db_url = _choose_url()
_connect_args = {"check_same_thread": False} if _db_url.startswith("sqlite") else {}

engine = create_engine(_db_url, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
