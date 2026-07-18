"""Admin panel API: users, roles, basic health/usage."""

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.database import (
    ChatSession,
    Connection,
    McpServer,
    Message,
    User,
    get_db,
)
from app.services import user_auth as auth

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminUserOut(BaseModel):
    id: str
    email: str
    role: str
    created_at: datetime
    session_count: int = 0


class AdminHealthOut(BaseModel):
    status: str
    users: int
    sessions: int
    messages: int
    connections: int
    mcp_servers: int
    time: str


@router.get("/users", response_model=List[AdminUserOut])
def list_users(admin: auth.CurrentAdmin, db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.asc()).all()
    out: List[AdminUserOut] = []
    for u in users:
        count = db.query(ChatSession).filter(ChatSession.user_id == u.id).count()
        out.append(
            AdminUserOut(
                id=u.id,
                email=u.email,
                role=u.role,
                created_at=u.created_at,
                session_count=count,
            )
        )
    return out


@router.patch("/users/{user_id}/role", response_model=AdminUserOut)
def update_user_role(
    user_id: str,
    body: auth.RoleUpdate,
    admin: auth.CurrentAdmin,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == admin.id and body.role != "admin":
        raise HTTPException(status_code=400, detail="Cannot demote yourself")

    if user.role == "admin" and body.role != "admin":
        admins = db.query(User).filter(User.role == "admin").count()
        if admins <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last admin")

    user.role = body.role
    db.commit()
    db.refresh(user)
    count = db.query(ChatSession).filter(ChatSession.user_id == user.id).count()
    return AdminUserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
        session_count=count,
    )


@router.get("/health", response_model=AdminHealthOut)
def admin_health(admin: auth.CurrentAdmin, db: Session = Depends(get_db)):
    return AdminHealthOut(
        status="ok",
        users=db.query(User).count(),
        sessions=db.query(ChatSession).count(),
        messages=db.query(Message).count(),
        connections=db.query(Connection).count(),
        mcp_servers=db.query(McpServer).count(),
        time=datetime.utcnow().isoformat() + "Z",
    )
