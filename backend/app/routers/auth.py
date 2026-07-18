"""User auth routes: register, login, logout, me, status."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.services import user_auth as auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/status", response_model=auth.AuthStatus)
def auth_status(db: Session = Depends(get_db)):
    has_users = auth.count_users(db) > 0
    return auth.AuthStatus(has_users=has_users, allow_register=True)


@router.post("/register", response_model=auth.AuthResponse)
def register(body: auth.RegisterRequest, response: Response, db: Session = Depends(get_db)):
    user, token = auth.register_user(db, body.email, body.password)
    response.set_cookie(
        key=auth.COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=auth.TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/",
    )
    return auth.AuthResponse(token=token, user=auth.user_to_out(user))


@router.post("/login", response_model=auth.AuthResponse)
def login(body: auth.LoginRequest, response: Response, db: Session = Depends(get_db)):
    user, token = auth.login_user(db, body.email, body.password)
    response.set_cookie(
        key=auth.COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=auth.TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/",
    )
    return auth.AuthResponse(token=token, user=auth.user_to_out(user))


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me", response_model=auth.UserOut)
def me(user: auth.CurrentUser):
    return auth.user_to_out(user)
