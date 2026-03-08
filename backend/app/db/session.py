import socket
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

SQLITE_FALLBACK_URL = "sqlite+pysqlite:////tmp/influencer_dev.db"


def _is_tcp_reachable(host: str, port: int, timeout: float = 0.6) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _resolved_database_url() -> str:
    raw_url = settings.database_url
    if not raw_url.startswith("postgresql"):
        return raw_url

    parsed = urlparse(raw_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432

    if _is_tcp_reachable(host, port):
        return raw_url

    if settings.db_fallback_to_sqlite:
        print(
            f"[db] Postgres {host}:{port} is unreachable. "
            f"Falling back to SQLite at {SQLITE_FALLBACK_URL}."
        )
        return SQLITE_FALLBACK_URL

    return raw_url


engine = create_engine(_resolved_database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
