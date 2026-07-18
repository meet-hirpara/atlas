"""Encrypted storage config on disk (survives primary DB switches)."""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from app.services.secret_store import decrypt_json, encrypt_json
from app.storage.types import (
    BackendConfig,
    BackendCredentials,
    EngineType,
    StorageConfig,
)

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(os.environ.get("ATLAS_STORAGE_CONFIG", "data/storage_config.json"))
_lock = threading.RLock()


def config_path() -> Path:
    return _CONFIG_PATH


def set_config_path(path: Path | str) -> None:
    """Test helper — redirect bootstrap file location."""
    global _CONFIG_PATH
    with _lock:
        _CONFIG_PATH = Path(path)


def _default_from_env() -> StorageConfig:
    from app.config import get_settings

    settings = get_settings()
    url = (settings.database_url or "").strip()
    cfg = StorageConfig(env_override_active=True)
    if url.startswith("postgresql") or url.startswith("postgres"):
        cfg.primary = BackendConfig(
            engine=EngineType.POSTGRESQL,
            credentials=BackendCredentials(url=url),
        )
    elif url.startswith("mysql"):
        cfg.primary = BackendConfig(
            engine=EngineType.MYSQL,
            credentials=BackendCredentials(url=url),
        )
    elif url.startswith("mongodb") or url.startswith("mongo://"):
        cfg.primary = BackendConfig(
            engine=EngineType.MONGODB,
            credentials=BackendCredentials(url=url),
        )
    else:
        path = url.replace("sqlite:///", "") if url.startswith("sqlite") else "./data/chatbot.db"
        cfg.primary = BackendConfig(
            engine=EngineType.SQLITE,
            credentials=BackendCredentials(path=path or "./data/chatbot.db"),
        )
    return cfg


def load_storage_config() -> StorageConfig:
    """Load active config; fall back to DATABASE_URL / default SQLite."""
    with _lock:
        if not _CONFIG_PATH.exists():
            return _default_from_env()
        try:
            raw = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            enc = raw.get("credentials_blob")
            if not enc:
                return _default_from_env()
            data = decrypt_json(enc)
            cfg = StorageConfig.model_validate(data)
            cfg.env_override_active = False
            return cfg
        except Exception as exc:
            logger.error("Failed to load storage_config.json: %s — using env default", exc)
            return _default_from_env()


def save_storage_config(cfg: StorageConfig) -> None:
    with _lock:
        os.makedirs(_CONFIG_PATH.parent, exist_ok=True)
        payload = cfg.model_dump(mode="json")
        payload["env_override_active"] = False
        blob = encrypt_json(payload)
        out = {
            "version": cfg.version,
            "credentials_blob": blob,
            "primary_engine": cfg.primary.engine.value,
            "chat_cache_engine": cfg.chat_cache.engine.value if cfg.chat_cache else None,
        }
        tmp = _CONFIG_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, indent=2), encoding="utf-8")
        tmp.replace(_CONFIG_PATH)
        logger.info(
            "Saved storage config (primary=%s, chat_cache=%s)",
            cfg.primary.engine.value,
            cfg.chat_cache.engine.value if cfg.chat_cache else None,
        )


def mask_credentials(creds: BackendCredentials) -> Dict[str, Any]:
    """Public view — never return secrets."""
    d = creds.model_dump()
    if d.get("password"):
        d["password"] = "••••••••"
    if d.get("url"):
        d["url"] = _mask_url(d["url"])
    return d


def _mask_url(url: str) -> str:
    if not url:
        return ""
    # hide password between ://user:PASSWORD@host
    try:
        if "://" in url and "@" in url:
            scheme, rest = url.split("://", 1)
            if "@" in rest and ":" in rest.split("@", 1)[0]:
                userinfo, hostpart = rest.split("@", 1)
                user = userinfo.split(":", 1)[0]
                return f"{scheme}://{user}:••••••••@{hostpart}"
    except Exception:
        pass
    return url[:12] + "…" if len(url) > 16 else url


def public_backend(cfg: Optional[BackendConfig]) -> Optional[Dict[str, Any]]:
    if not cfg:
        return None
    return {
        "engine": cfg.engine.value,
        "enabled": cfg.enabled,
        "credentials": mask_credentials(cfg.credentials),
    }
