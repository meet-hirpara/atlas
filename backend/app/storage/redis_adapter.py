"""Redis adapter: ping + optional conversation-history store."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus

from app.storage.types import BackendConfig, BackendCredentials, EngineType

logger = logging.getLogger(__name__)

MSG_KEY = "atlas:chat:msgs:{session_id}"
SESSION_SET = "atlas:chat:sessions"


def _redis_url(creds: BackendCredentials) -> str:
    if creds.url and creds.url.strip():
        return creds.url.strip()
    host = creds.host or "127.0.0.1"
    port = creds.port or 6379
    db = 0
    if creds.database and str(creds.database).isdigit():
        db = int(creds.database)
    password = creds.password or ""
    user = creds.username or ""
    if password:
        auth = f"{quote_plus(user)}:{quote_plus(password)}@" if user else f":{quote_plus(password)}@"
        return f"redis://{auth}{host}:{port}/{db}"
    return f"redis://{host}:{port}/{db}"


def get_redis(creds: BackendCredentials):
    try:
        import redis
    except ImportError as exc:
        raise ImportError("redis is required for Redis storage") from exc
    return redis.Redis.from_url(_redis_url(creds), decode_responses=True, socket_connect_timeout=5)


def ping_redis(creds: BackendCredentials) -> Tuple[bool, str, float]:
    t0 = time.perf_counter()
    try:
        client = get_redis(creds)
        client.ping()
        client.close()
        return True, "Connection OK", (time.perf_counter() - t0) * 1000
    except ImportError as exc:
        return False, f"Missing driver: install redis ({exc})", (time.perf_counter() - t0) * 1000
    except Exception as exc:
        return False, str(exc), (time.perf_counter() - t0) * 1000


def ensure_redis_ready(creds: BackendCredentials) -> None:
    """Redis has no schema — ping + set a marker key."""
    client = get_redis(creds)
    try:
        client.ping()
        client.set("atlas:storage:ready", "1", ex=86400)
        logger.info("Redis chat-cache ready at %s", _redis_url(creds).split("@")[-1])
    finally:
        client.close()


def apply_redis_backend(cfg: BackendConfig):
    if cfg.engine != EngineType.REDIS:
        raise ValueError("Redis adapter requires redis engine")
    ensure_redis_ready(cfg.credentials)
    return get_redis(cfg.credentials)


def _serialize_msg(msg: Any) -> str:
    created = getattr(msg, "created_at", None)
    if isinstance(created, datetime):
        created_s = created.isoformat()
    else:
        created_s = str(created or "")
    return json.dumps(
        {
            "id": getattr(msg, "id", ""),
            "session_id": getattr(msg, "session_id", ""),
            "role": getattr(msg, "role", ""),
            "content": getattr(msg, "content", ""),
            "sources": getattr(msg, "sources", "") or "",
            "created_at": created_s,
        }
    )


def _hydrate_msg(data: Dict[str, Any]):
    from app.models.database import Message

    created_raw = data.get("created_at") or ""
    created: Optional[datetime] = None
    if created_raw:
        try:
            created = datetime.fromisoformat(created_raw.replace("Z", ""))
        except ValueError:
            created = datetime.utcnow()
    return Message(
        id=data.get("id") or "",
        session_id=data.get("session_id") or "",
        role=data.get("role") or "",
        content=data.get("content") or "",
        sources=data.get("sources") or "",
        created_at=created or datetime.utcnow(),
    )


class RedisChatHistory:
    """Optional conversation-history backend keyed by session id."""

    def __init__(self, client):
        self._r = client

    def append(self, msg: Any) -> None:
        key = MSG_KEY.format(session_id=msg.session_id)
        self._r.rpush(key, _serialize_msg(msg))
        self._r.sadd(SESSION_SET, msg.session_id)

    def list_messages(self, session_id: str) -> List[Any]:
        key = MSG_KEY.format(session_id=session_id)
        raw = self._r.lrange(key, 0, -1)
        out: List[Any] = []
        for item in raw:
            try:
                out.append(_hydrate_msg(json.loads(item)))
            except Exception as exc:
                logger.warning("Skip bad Redis message: %s", exc)
        return out

    def delete_session(self, session_id: str) -> None:
        self._r.delete(MSG_KEY.format(session_id=session_id))
        self._r.srem(SESSION_SET, session_id)

    def close(self) -> None:
        try:
            self._r.close()
        except Exception:
            pass
