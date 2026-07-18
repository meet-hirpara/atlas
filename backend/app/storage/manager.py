"""Runtime storage manager: connect, schema ensure, hot-swap primary + chat cache."""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from app.storage.config_store import load_storage_config, public_backend, save_storage_config
from app.storage.mongo_adapter import apply_mongo_backend, ping_mongo
from app.storage.redis_adapter import RedisChatHistory, apply_redis_backend, ping_redis
from app.storage.sql_adapter import apply_sql_backend, ping_sql
from app.storage.types import (
    CACHE_ENGINES,
    DOCUMENT_ENGINES,
    SQL_ENGINES,
    BackendConfig,
    BackendCredentials,
    DataPlacement,
    EngineType,
    Purpose,
    StorageApplyRequest,
    StorageConfig,
    StorageStatusOut,
    StorageTestRequest,
    StorageTestResult,
)

logger = logging.getLogger(__name__)

DESTRUCTIVE_WARNING = (
    "Switching the primary database starts fresh: all existing data is left behind "
    "(users, admins, chats, connections, workspace). You must create a new admin account "
    "after switching. There is no automatic migration."
)


class StorageManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._config: StorageConfig = StorageConfig()
        self._primary_mode: str = "sql"  # sql | mongo
        self._redis_chat: Optional[RedisChatHistory] = None
        self._mongo_client = None
        self._mongo_db_name: Optional[str] = None
        self._started = False

    @property
    def config(self) -> StorageConfig:
        return self._config

    @property
    def primary_mode(self) -> str:
        return self._primary_mode

    @property
    def redis_chat(self) -> Optional[RedisChatHistory]:
        return self._redis_chat

    @property
    def mongo_handle(self):
        return self._mongo_client, self._mongo_db_name

    def startup(self) -> None:
        """Load config and bind backends. Safe to call once from FastAPI startup."""
        with self._lock:
            if self._started:
                return
            self._config = load_storage_config()
            self._apply_primary(self._config.primary, persist=False)
            self._apply_chat_cache(self._config.chat_cache, persist=False)
            self._started = True
            logger.info(
                "Storage ready: primary=%s mode=%s chat_cache=%s",
                self._config.primary.engine.value,
                self._primary_mode,
                self._config.chat_cache.engine.value if self._config.chat_cache else "none",
            )

    def status(self) -> StorageStatusOut:
        cfg = self._config
        placement = [
            DataPlacement(
                purpose="users_roles_admin",
                description="Users, roles, and admin accounts",
                engine=cfg.primary.engine.value,
                location_hint=_location_hint(cfg.primary),
            ),
            DataPlacement(
                purpose="workspace",
                description="Projects, proposals, jobs, clients, artifacts",
                engine=cfg.primary.engine.value,
                location_hint=_location_hint(cfg.primary),
            ),
            DataPlacement(
                purpose="connections_mcp",
                description="Integrations and MCP servers",
                engine=cfg.primary.engine.value,
                location_hint=_location_hint(cfg.primary),
            ),
        ]
        if cfg.chat_cache and cfg.chat_cache.enabled:
            placement.append(
                DataPlacement(
                    purpose="conversation_history",
                    description="Chat messages (optional Redis / alternate store)",
                    engine=cfg.chat_cache.engine.value,
                    location_hint=_location_hint(cfg.chat_cache),
                )
            )
        else:
            placement.append(
                DataPlacement(
                    purpose="conversation_history",
                    description="Chat sessions and messages (on primary)",
                    engine=cfg.primary.engine.value,
                    location_hint=_location_hint(cfg.primary),
                )
            )

        from app.config import get_settings

        return StorageStatusOut(
            primary=public_backend(cfg.primary) or {},
            chat_cache=public_backend(cfg.chat_cache),
            placement=placement,
            env_database_url=_mask_env_url(get_settings().database_url),
            warning=DESTRUCTIVE_WARNING,
            engines_available=_engines_available(),
        )

    def test_connection(self, req: StorageTestRequest) -> StorageTestResult:
        engine = req.engine
        creds = req.credentials
        if engine in SQL_ENGINES:
            ok, msg, ms = ping_sql(engine, creds)
        elif engine == EngineType.MONGODB:
            ok, msg, ms = ping_mongo(creds)
        elif engine == EngineType.REDIS:
            ok, msg, ms = ping_redis(creds)
        else:
            return StorageTestResult(ok=False, engine=engine, message=f"Unknown engine {engine}")
        return StorageTestResult(ok=ok, engine=engine, message=msg, latency_ms=round(ms, 2))

    def apply(self, req: StorageApplyRequest) -> StorageStatusOut:
        if not req.confirm_destructive or not req.acknowledge_data_loss:
            raise ValueError(
                "Applying a new primary store is destructive. Set confirm_destructive=true "
                "and acknowledge_data_loss=true after reading the warning."
            )
        self._validate_primary(req.primary)
        if req.chat_cache and req.chat_cache.enabled:
            self._validate_chat_cache(req.chat_cache)

        with self._lock:
            # Test before commit
            primary_test = self.test_connection(
                StorageTestRequest(
                    engine=req.primary.engine,
                    credentials=req.primary.credentials,
                    purpose=Purpose.PRIMARY,
                )
            )
            if not primary_test.ok:
                raise ConnectionError(f"Primary connection failed: {primary_test.message}")

            if req.chat_cache and req.chat_cache.enabled:
                cache_test = self.test_connection(
                    StorageTestRequest(
                        engine=req.chat_cache.engine,
                        credentials=req.chat_cache.credentials,
                        purpose=Purpose.CHAT_CACHE,
                    )
                )
                if not cache_test.ok:
                    raise ConnectionError(f"Chat cache connection failed: {cache_test.message}")

            self._apply_primary(req.primary, persist=False)
            self._apply_chat_cache(req.chat_cache if req.chat_cache and req.chat_cache.enabled else None, persist=False)
            new_cfg = StorageConfig(
                version=1,
                primary=req.primary,
                chat_cache=req.chat_cache if req.chat_cache and req.chat_cache.enabled else None,
                env_override_active=False,
            )
            save_storage_config(new_cfg)
            self._config = new_cfg
            self._started = True
            logger.warning(
                "Storage switched — primary=%s. Existing data on the previous store is not migrated.",
                req.primary.engine.value,
            )
            return self.status()

    def _validate_primary(self, cfg: BackendConfig) -> None:
        if cfg.engine not in SQL_ENGINES and cfg.engine not in DOCUMENT_ENGINES:
            raise ValueError(
                f"Primary must be sqlite, postgresql, mysql, or mongodb — got {cfg.engine.value}"
            )
        if cfg.engine == EngineType.REDIS:
            raise ValueError("Redis cannot be the primary store; use it as chat cache only")

    def _validate_chat_cache(self, cfg: BackendConfig) -> None:
        if cfg.engine not in CACHE_ENGINES and cfg.engine not in SQL_ENGINES:
            raise ValueError(f"Chat cache engine not supported: {cfg.engine.value}")
        # Prefer Redis for chat cache; Mongo also allowed per types
        if cfg.engine not in (EngineType.REDIS, EngineType.MONGODB):
            raise ValueError("Chat cache should be redis (recommended) or mongodb")

    def _apply_primary(self, cfg: BackendConfig, *, persist: bool) -> None:
        from app.models import database as dbmod

        if cfg.engine in SQL_ENGINES:
            eng = apply_sql_backend(cfg)
            dbmod.rebind_sql_engine(eng)
            self._primary_mode = "sql"
            self._mongo_client = None
            self._mongo_db_name = None
            # Run lightweight SQLite migrations when applicable
            dbmod.init_db(run_sqlite_migrations=cfg.engine == EngineType.SQLITE)
        elif cfg.engine == EngineType.MONGODB:
            client, db_name = apply_mongo_backend(cfg)
            dbmod.rebind_mongo(client, db_name)
            self._primary_mode = "mongo"
            self._mongo_client = client
            self._mongo_db_name = db_name
        else:
            raise ValueError(f"Unsupported primary engine {cfg.engine}")

        if persist:
            self._config.primary = cfg
            save_storage_config(self._config)

    def _apply_chat_cache(self, cfg: Optional[BackendConfig], *, persist: bool) -> None:
        if self._redis_chat:
            try:
                self._redis_chat.close()
            except Exception:
                pass
            self._redis_chat = None

        if not cfg or not cfg.enabled:
            if persist:
                self._config.chat_cache = None
                save_storage_config(self._config)
            return

        if cfg.engine == EngineType.REDIS:
            client = apply_redis_backend(cfg)
            self._redis_chat = RedisChatHistory(client)
        elif cfg.engine == EngineType.MONGODB:
            # Chat on a separate Mongo is unusual; ensure collections exist for reuse
            apply_mongo_backend(cfg)
            logger.info("Mongo chat_cache configured (messages still dual-written to primary)")
        else:
            raise ValueError(f"Unsupported chat_cache engine {cfg.engine}")

        if persist:
            self._config.chat_cache = cfg
            save_storage_config(self._config)


def _location_hint(cfg: BackendConfig) -> str:
    c = cfg.credentials
    if c.url:
        return c.url.split("@")[-1][:80] if "@" in c.url else c.url[:80]
    if cfg.engine == EngineType.SQLITE:
        return c.path or "./data/chatbot.db"
    host = c.host or "127.0.0.1"
    port = c.port or 0
    db = c.database or ""
    return f"{host}:{port}/{db}" if port else f"{host}/{db}"


def _mask_env_url(url: str) -> str:
    if not url:
        return ""
    if "://" in url and "@" in url:
        scheme, rest = url.split("://", 1)
        if "@" in rest:
            return f"{scheme}://••••@{rest.split('@', 1)[1]}"
    return url


def _engines_available() -> List[Dict[str, Any]]:
    def _try(label: str, probe) -> Dict[str, Any]:
        try:
            probe()
            return {"engine": label, "driver_installed": True}
        except Exception as exc:
            return {"engine": label, "driver_installed": False, "hint": str(exc)[:120]}

    out = [
        {"engine": "sqlite", "driver_installed": True},
        _try("postgresql", lambda: __import__("psycopg2")),
        _try("mysql", lambda: __import__("pymysql")),
        _try("mongodb", lambda: __import__("pymongo")),
        _try("redis", lambda: __import__("redis")),
    ]
    return out


storage_manager = StorageManager()


def get_storage_manager() -> StorageManager:
    return storage_manager
