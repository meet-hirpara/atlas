"""SQLAlchemy engine factory for SQLite / PostgreSQL / MySQL."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional, Tuple
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.storage.types import BackendConfig, BackendCredentials, EngineType

logger = logging.getLogger(__name__)


def build_sqlalchemy_url(engine: EngineType, creds: BackendCredentials) -> str:
    if creds.url and creds.url.strip():
        url = creds.url.strip()
        # Normalize postgres scheme for SQLAlchemy
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        return url

    if engine == EngineType.SQLITE:
        path = (creds.path or "./data/chatbot.db").strip()
        if not path.startswith("./") and not os.path.isabs(path) and not path.startswith("sqlite"):
            path = "./" + path
        if path.startswith("sqlite:"):
            return path
        return f"sqlite:///{path}"

    host = creds.host or "127.0.0.1"
    user = quote_plus(creds.username or "")
    password = quote_plus(creds.password or "")
    db = creds.database or "atlas"
    auth = f"{user}:{password}@" if user or password else ""

    if engine == EngineType.POSTGRESQL:
        port = creds.port or 5432
        return f"postgresql+psycopg2://{auth}{host}:{port}/{db}"

    if engine == EngineType.MYSQL:
        port = creds.port or 3306
        return f"mysql+pymysql://{auth}{host}:{port}/{db}"

    raise ValueError(f"Not a SQL engine: {engine}")


def create_sql_engine(engine_type: EngineType, creds: BackendCredentials) -> Engine:
    url = build_sqlalchemy_url(engine_type, creds)
    connect_args: dict = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        # Ensure parent dir exists
        path = url.replace("sqlite:///", "")
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)


def ping_sql(engine_type: EngineType, creds: BackendCredentials) -> Tuple[bool, str, float]:
    t0 = time.perf_counter()
    try:
        eng = create_sql_engine(engine_type, creds)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        eng.dispose()
        return True, "Connection OK", (time.perf_counter() - t0) * 1000
    except ImportError as exc:
        driver = "psycopg2" if engine_type == EngineType.POSTGRESQL else "pymysql"
        return (
            False,
            f"Missing driver for {engine_type.value}: install {driver} ({exc})",
            (time.perf_counter() - t0) * 1000,
        )
    except Exception as exc:
        return False, str(exc), (time.perf_counter() - t0) * 1000


def ensure_sql_schema(eng: Engine) -> None:
    """Create missing tables via SQLAlchemy metadata."""
    from app.models.database import Base

    Base.metadata.create_all(bind=eng)
    logger.info("SQL schema ensure_all complete for %s", eng.url.render_as_string(hide_password=True))


def apply_sql_backend(cfg: BackendConfig) -> Engine:
    if cfg.engine not in (EngineType.SQLITE, EngineType.POSTGRESQL, EngineType.MYSQL):
        raise ValueError(f"SQL adapter cannot apply engine {cfg.engine}")
    eng = create_sql_engine(cfg.engine, cfg.credentials)
    ensure_sql_schema(eng)
    return eng
