import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.integrations.registry import PROVIDER_IDS, get_provider
from app.models.database import Connection
from app.services.secret_store import decrypt_json, encrypt_json

logger = logging.getLogger(__name__)


def _mask_email(email: str) -> str:
    if "@" not in email:
        return email[:3] + "***"
    local, domain = email.split("@", 1)
    return f"{local[:2]}***@{domain}"


def _load_credentials(row: Connection) -> Dict[str, Any]:
    try:
        return decrypt_json(row.credentials)
    except Exception as exc:
        logger.error("Failed to decrypt credentials for provider=%s: %s", row.provider, exc)
        raise


def _user_rows(db: Session, user_id: Optional[str]) -> List[Connection]:
    q = db.query(Connection)
    if user_id:
        q = q.filter(Connection.user_id == user_id)
    return q.all()


def list_connections(db: Session, user_id: Optional[str] = None) -> List[dict]:
    rows = _user_rows(db, user_id)
    by_provider = {r.provider: r for r in rows}
    result = []
    for p in PROVIDER_IDS:
        row = by_provider.get(p)
        provider_def = get_provider(p)
        if row:
            try:
                creds = _load_credentials(row)
            except Exception:
                creds = {}
            label = row.label
            if not label and provider_def:
                try:
                    label = provider_def.build_label(creds)
                except Exception as exc:
                    logger.warning("build_label failed for %s: %s", p, exc)
                    label = p
            result.append({
                "provider": p,
                "connected": True,
                "label": label,
                "connected_at": row.connected_at.isoformat() if row.connected_at else None,
            })
        else:
            result.append({"provider": p, "connected": False, "label": "", "connected_at": None})
    return result


def get_credentials(
    db: Session, provider: str, user_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    q = db.query(Connection).filter(Connection.provider == provider)
    if user_id:
        q = q.filter(Connection.user_id == user_id)
    row = q.first()
    if not row:
        return None
    return _load_credentials(row)


def save_connection(
    db: Session,
    provider: str,
    credentials: dict,
    label: str = "",
    user_id: Optional[str] = None,
) -> List[dict]:
    q = db.query(Connection).filter(Connection.provider == provider)
    if user_id:
        q = q.filter(Connection.user_id == user_id)
    else:
        q = q.filter(Connection.user_id.is_(None))
    row = q.first()
    now = datetime.utcnow()
    payload = encrypt_json(credentials)

    if row:
        row.credentials = payload
        row.label = label
        row.updated_at = now
        if user_id and not row.user_id:
            row.user_id = user_id
    else:
        row = Connection(
            id=str(uuid.uuid4()),
            provider=provider,
            user_id=user_id,
            label=label,
            credentials=payload,
            connected_at=now,
            updated_at=now,
        )
        db.add(row)

    db.commit()
    logger.info("Saved encrypted credentials for provider=%s user=%s", provider, user_id)
    return list_connections(db, user_id=user_id)


def delete_connection(
    db: Session, provider: str, user_id: Optional[str] = None
) -> bool:
    q = db.query(Connection).filter(Connection.provider == provider)
    if user_id:
        q = q.filter(Connection.user_id == user_id)
    else:
        q = q.filter(Connection.user_id.is_(None))
    row = q.first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    logger.info("Deleted connection provider=%s user=%s", provider, user_id)
    return True


def get_all_credentials(
    db: Session, user_id: Optional[str] = None
) -> Dict[str, Dict[str, Any]]:
    rows = _user_rows(db, user_id)
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        try:
            out[r.provider] = _load_credentials(r)
        except Exception as exc:
            logger.error("Skipping undecryptable credentials for %s: %s", r.provider, exc)
    return out
