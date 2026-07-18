"""Localhost API auth token for sensitive endpoints (code run, MCP connect)."""

from __future__ import annotations

import logging
import secrets
from pathlib import Path
from typing import Optional

from fastapi import Header, HTTPException, Request

logger = logging.getLogger(__name__)

TOKEN_HEADER = "X-Atlas-Token"
_TOKEN_FILE = Path("data/local_auth_token")
_cached_token: Optional[str] = None


def _read_token_file() -> Optional[str]:
    try:
        if _TOKEN_FILE.is_file():
            value = _TOKEN_FILE.read_text(encoding="utf-8").strip()
            return value or None
    except OSError as exc:
        logger.warning("Could not read local auth token file: %s", exc)
    return None


def _write_token_file(token: str) -> None:
    try:
        _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _TOKEN_FILE.write_text(token, encoding="utf-8")
    except OSError as exc:
        logger.error("Could not persist local auth token: %s", exc)


def get_local_auth_token() -> str:
    """Return the shared local auth token, generating one if needed."""
    global _cached_token
    if _cached_token:
        return _cached_token

    from app.config import get_settings

    env_token = (get_settings().atlas_local_auth_token or "").strip()
    if env_token:
        _cached_token = env_token
        return _cached_token

    file_token = _read_token_file()
    if file_token:
        _cached_token = file_token
        return _cached_token

    token = secrets.token_urlsafe(32)
    _write_token_file(token)
    _cached_token = token
    logger.info("Generated local auth token at %s", _TOKEN_FILE)
    return token


def is_loopback_request(request: Request) -> bool:
    client = request.client.host if request.client else ""
    return client in {"127.0.0.1", "::1", "localhost"}


def require_local_auth(
    request: Request,
    x_atlas_token: Optional[str] = Header(default=None, alias=TOKEN_HEADER),
) -> None:
    """Dependency: require X-Atlas-Token matching the local token."""
    expected = get_local_auth_token()
    provided = (x_atlas_token or "").strip()
    if provided and secrets.compare_digest(provided, expected):
        return
    # Soft-fail only for missing header on non-loopback would be worse —
    # always require the token for gated routes.
    logger.warning(
        "Local auth rejected for %s %s from %s",
        request.method,
        request.url.path,
        request.client.host if request.client else "?",
    )
    raise HTTPException(
        status_code=401,
        detail=f"Missing or invalid {TOKEN_HEADER}. Fetch a token from GET /api/auth/token.",
    )
