"""MongoDB adapter: ping, schema/indexes, lightweight session for ORM-shaped access."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.storage.types import BackendConfig, BackendCredentials, EngineType

logger = logging.getLogger(__name__)

# Collection names mirror SQLAlchemy __tablename__
COLLECTIONS: Dict[str, List[tuple]] = {
    "users": [("email", True), ("role", False)],
    "clients": [("user_id", False)],
    "projects": [("user_id", False), ("client_id", False)],
    "chat_sessions": [("user_id", False), ("project_id", False), ("updated_at", False)],
    "session_agents": [("session_id", False)],
    "messages": [("session_id", False), ("created_at", False)],
    "connections": [("user_id", False), ("provider", False)],
    "mcp_servers": [("user_id", False)],
    "github_repos": [("user_id", False)],
    "uploaded_documents": [("session_id", False)],
    "proposals": [("user_id", False)],
    "job_inbox": [("user_id", False)],
    "artifacts": [("session_id", False), ("user_id", False)],
    "scheduled_research": [("user_id", False)],
    "audit_log": [("created_at", False)],
}


def _mongo_uri(creds: BackendCredentials) -> str:
    if creds.url and creds.url.strip():
        return creds.url.strip()
    host = creds.host or "127.0.0.1"
    port = creds.port or 27017
    db = creds.database or "atlas"
    user = creds.username or ""
    password = creds.password or ""
    if user:
        from urllib.parse import quote_plus

        return f"mongodb://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{db}"
    return f"mongodb://{host}:{port}/{db}"


def _db_name(creds: BackendCredentials) -> str:
    if creds.database:
        return creds.database
    if creds.url and "/" in creds.url.rstrip("/"):
        return creds.url.rstrip("/").rsplit("/", 1)[-1].split("?")[0] or "atlas"
    return "atlas"


def get_client(creds: BackendCredentials):
    try:
        from pymongo import MongoClient
    except ImportError as exc:
        raise ImportError("pymongo is required for MongoDB storage") from exc
    return MongoClient(_mongo_uri(creds), serverSelectionTimeoutMS=5000)


def ping_mongo(creds: BackendCredentials) -> Tuple[bool, str, float]:
    t0 = time.perf_counter()
    try:
        client = get_client(creds)
        client.admin.command("ping")
        client.close()
        return True, "Connection OK", (time.perf_counter() - t0) * 1000
    except ImportError as exc:
        return False, f"Missing driver: install pymongo ({exc})", (time.perf_counter() - t0) * 1000
    except Exception as exc:
        return False, str(exc), (time.perf_counter() - t0) * 1000


def ensure_mongo_schema(creds: BackendCredentials) -> None:
    client = get_client(creds)
    try:
        db = client[_db_name(creds)]
        existing = set(db.list_collection_names())
        for name, indexes in COLLECTIONS.items():
            if name not in existing:
                db.create_collection(name)
            coll = db[name]
            for field, unique in indexes:
                coll.create_index(field, unique=unique, background=True)
        logger.info("Mongo schema ensured (%s collections) on db=%s", len(COLLECTIONS), _db_name(creds))
    finally:
        client.close()


def apply_mongo_backend(cfg: BackendConfig):
    if cfg.engine != EngineType.MONGODB:
        raise ValueError("Mongo adapter requires mongodb engine")
    ensure_mongo_schema(cfg.credentials)
    return get_client(cfg.credentials), _db_name(cfg.credentials)


# ── Lightweight Mongo session (common SQLAlchemy Session patterns) ──────────


def _serialize(obj: Any) -> Dict[str, Any]:
    from sqlalchemy import inspect as sa_inspect

    mapper = sa_inspect(type(obj))
    data: Dict[str, Any] = {}
    for col in mapper.columns:
        val = getattr(obj, col.key, None)
        if isinstance(val, datetime):
            data[col.key] = val
        else:
            data[col.key] = val
    return data


def _hydrate(model: type, doc: Dict[str, Any]) -> Any:
    doc = dict(doc)
    doc.pop("_id", None)
    obj = model.__new__(model)
    # bypass __init__ side effects
    for k, v in doc.items():
        try:
            setattr(obj, k, v)
        except Exception:
            pass
    # ensure all columns exist
    from sqlalchemy import inspect as sa_inspect

    for col in sa_inspect(model).columns:
        if not hasattr(obj, col.key):
            setattr(obj, col.key, None)
    return obj


class _MongoQuery:
    def __init__(self, session: "MongoSession", model: type):
        self._session = session
        self._model = model
        self._filters: List[Dict[str, Any]] = []
        self._order: List[tuple] = []
        self._limit: Optional[int] = None

    def _col_key(self, expr: Any) -> str:
        return getattr(expr, "key", None) or getattr(expr, "name", str(expr))

    def filter(self, *criteria):
        for c in criteria:
            self._filters.append(self._criterion_to_mongo(c))
        return self

    def filter_by(self, **kwargs):
        self._filters.append(kwargs)
        return self

    def _criterion_to_mongo(self, c: Any) -> Dict[str, Any]:
        # Column == value
        left = getattr(c, "left", None)
        right = getattr(c, "right", None)
        op = getattr(getattr(c, "operator", None), "__name__", "") or str(getattr(c, "operator", ""))

        # .is_(None) / IS NULL
        if type(c).__name__ in ("Is", "IsDistinctFrom") or "is_" in op.lower() or op in ("is_", "is"):
            key = self._col_key(getattr(c, "left", c) if left is None else left)
            # SQLAlchemy UnaryExpression for IS NULL
            try:
                from sqlalchemy.sql import operators

                if getattr(c, "operator", None) is operators.is_ and right is not None:
                    val = getattr(right, "value", right)
                    if val is None:
                        return {key: None}
            except Exception:
                pass
            # BinaryExpression left IS NULL
            if right is not None and getattr(right, "value", right) is None:
                return {self._col_key(left): None}

        if left is not None and right is not None:
            key = self._col_key(left)
            val = getattr(right, "value", right)
            # equality
            if op in ("eq", "==", "eq_") or "eq" in op:
                return {key: val}
            if op in ("ne", "!=") or "ne" in op:
                return {key: {"$ne": val}}
            if "gt" == op or op == ">":
                return {key: {"$gt": val}}
            if "lt" == op or op == "<":
                return {key: {"$lt": val}}
            if "ge" in op or op == ">=":
                return {key: {"$gte": val}}
            if "le" in op or op == "<=":
                return {key: {"$lte": val}}

        # BooleanClauseList (AND)
        clauses = getattr(c, "clauses", None)
        if clauses:
            merged: Dict[str, Any] = {}
            for sub in clauses:
                merged.update(self._criterion_to_mongo(sub))
            return merged

        logger.warning("Unsupported Mongo filter criterion: %r — ignored", c)
        return {}

    def order_by(self, *exprs):
        for e in exprs:
            # desc()
            modifier = getattr(e, "modifier", None)
            element = getattr(e, "element", e)
            key = self._col_key(element)
            direction = -1 if (modifier is not None or type(e).__name__ == "UnaryExpression" and "desc" in str(e).lower()) else 1
            if hasattr(e, "modifier") or str(type(e).__name__) == "UnaryExpression":
                # SQLAlchemy desc() wraps element
                from sqlalchemy.sql.elements import UnaryExpression

                if isinstance(e, UnaryExpression):
                    key = self._col_key(e.element)
                    direction = -1 if "DESC" in str(e).upper() else 1
            self._order.append((key, direction))
        return self

    def limit(self, n: int):
        self._limit = n
        return self

    def _mongo_filter(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for f in self._filters:
            out.update(f)
        return out

    def _coll(self):
        table = self._model.__tablename__
        return self._session.db[table]

    def first(self):
        cur = self._coll().find(self._mongo_filter())
        if self._order:
            cur = cur.sort(self._order)
        doc = next(cur.limit(1), None)
        return _hydrate(self._model, doc) if doc else None

    def all(self):
        cur = self._coll().find(self._mongo_filter())
        if self._order:
            cur = cur.sort(self._order)
        if self._limit:
            cur = cur.limit(self._limit)
        return [_hydrate(self._model, d) for d in cur]

    def count(self) -> int:
        return self._coll().count_documents(self._mongo_filter())

    def delete(self, synchronize_session=False):
        result = self._coll().delete_many(self._mongo_filter())
        return result.deleted_count

    def update(self, values: Dict[str, Any], synchronize_session=False):
        # values may be {Model.col: v} or {str: v}
        payload = {}
        for k, v in values.items():
            key = k if isinstance(k, str) else getattr(k, "key", str(k))
            payload[key] = v
        result = self._coll().update_many(self._mongo_filter(), {"$set": payload})
        return result.modified_count


class MongoSession:
    """Subset of SQLAlchemy Session API backed by MongoDB collections."""

    def __init__(self, client, db_name: str):
        self._client = client
        self.db = client[db_name]
        self._pending_add: List[Any] = []
        self._pending_delete: List[Any] = []

    def query(self, model: type) -> _MongoQuery:
        return _MongoQuery(self, model)

    def add(self, obj: Any) -> None:
        self._pending_add.append(obj)

    def delete(self, obj: Any) -> None:
        self._pending_delete.append(obj)

    def commit(self) -> None:
        for obj in self._pending_add:
            table = obj.__tablename__
            data = _serialize(obj)
            pk = data.get("id")
            if pk:
                self.db[table].replace_one({"id": pk}, data, upsert=True)
            else:
                self.db[table].insert_one(data)
        for obj in self._pending_delete:
            table = obj.__tablename__
            pk = getattr(obj, "id", None)
            if pk is not None:
                self.db[table].delete_one({"id": pk})
        self._pending_add.clear()
        self._pending_delete.clear()

    def refresh(self, obj: Any) -> None:
        table = obj.__tablename__
        pk = getattr(obj, "id", None)
        if pk is None:
            return
        doc = self.db[table].find_one({"id": pk})
        if not doc:
            return
        doc.pop("_id", None)
        for k, v in doc.items():
            setattr(obj, k, v)

    def close(self) -> None:
        self._pending_add.clear()
        self._pending_delete.clear()

    def flush(self) -> None:
        self.commit()
