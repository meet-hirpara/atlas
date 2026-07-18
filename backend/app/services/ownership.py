"""Shared multi-user ownership helpers."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.database import ChatSession, User
from app.services import chat_service


def owned_session_or_404(db: Session, session_id: str, user: User) -> ChatSession:
    """Return session if owned by user (or admin). Orphan (NULL user_id) sessions are admin-only."""
    session = chat_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if user.role == "admin":
        return session
    if session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def row_owned(row: Any, user: User, *, admin_ok: bool = True) -> bool:
    if row is None:
        return False
    if admin_ok and user.role == "admin":
        return True
    return getattr(row, "user_id", None) == user.id


def require_row_owned(row: Any, user: User, *, detail: str = "Not found") -> Any:
    if not row_owned(row, user):
        raise HTTPException(status_code=404, detail=detail)
    return row


def owned_query(query, model, user_id: Optional[str]):
    """Filter a SQLAlchemy query to rows owned by user_id when provided."""
    if user_id:
        return query.filter(model.user_id == user_id)
    return query
