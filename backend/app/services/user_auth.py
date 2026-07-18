"""User account auth: bcrypt passwords + JWT bearer tokens."""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.database import User, get_db

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 14
COOKIE_NAME = "atlas_session"
_bearer = HTTPBearer(auto_error=False)

Role = Literal["user", "admin"]


def _normalize_email(value: str) -> str:
    email = (value or "").strip().lower()
    if "@" not in email or "." not in email.split("@")[-1] or len(email) < 5:
        raise ValueError("Invalid email address")
    return email


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return _normalize_email(v)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return _normalize_email(v)


class UserOut(BaseModel):
    id: str
    email: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class AuthStatus(BaseModel):
    has_users: bool
    allow_register: bool


class AuthResponse(BaseModel):
    token: str
    user: UserOut


class RoleUpdate(BaseModel):
    role: Role


def _jwt_secret() -> str:
    settings = get_settings()
    secret = (settings.atlas_jwt_secret or "").strip()
    if secret:
        return secret
    # Stable fallback for local installs (derived from local auth token material)
    from app.services.local_auth import get_local_auth_token

    return f"atlas-jwt:{get_local_auth_token()}"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=TOKEN_EXPIRE_DAYS)).timestamp()),
        "jti": secrets.token_urlsafe(8),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


def user_to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
    )


def count_users(db: Session) -> int:
    return db.query(User).count()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email.lower().strip()).first()


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def get_first_admin(db: Session) -> Optional[User]:
    return (
        db.query(User)
        .filter(User.role == "admin")
        .order_by(User.created_at.asc())
        .first()
    )


def register_user(db: Session, email: str, password: str) -> tuple[User, str]:
    email_norm = email.lower().strip()
    if get_user_by_email(db, email_norm):
        raise HTTPException(status_code=400, detail="Email already registered")

    is_first = count_users(db) == 0
    user = User(
        id=str(uuid.uuid4()),
        email=email_norm,
        password_hash=hash_password(password),
        role="admin" if is_first else "user",
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if is_first:
        from app.models.database import assign_orphaned_data_to_user

        assign_orphaned_data_to_user(db, user.id)
        logger.info("First user %s registered as admin; orphaned data assigned", user.email)

    token = create_access_token(user.id, user.role)
    return user, token


def login_user(db: Session, email: str, password: str) -> tuple[User, str]:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user.id, user.role)
    return user, token


def extract_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials],
) -> Optional[str]:
    if credentials and credentials.scheme.lower() == "bearer" and credentials.credentials:
        return credentials.credentials.strip()
    cookie = request.cookies.get(COOKIE_NAME)
    if cookie:
        return cookie.strip()
    return None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> User:
    token = extract_token(request, credentials)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAdmin = Annotated[User, Depends(get_current_admin)]
