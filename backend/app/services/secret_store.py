"""At-rest encryption for integration / MCP credentials (Fernet)."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from functools import lru_cache
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

ENC_PREFIX = "enc:v1:"


def _derive_fernet_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache
def _fernet() -> Optional[Fernet]:
    from app.config import get_settings

    secret = (get_settings().atlas_secret_key or "").strip()
    if not secret:
        # Dev fallback: stable per-machine key so local installs still encrypt.
        # Prefer setting ATLAS_SECRET_KEY in .env for real deployments.
        machine = os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "atlas-local"
        secret = f"atlas-dev-key:{machine}"
        logger.warning(
            "ATLAS_SECRET_KEY not set — using derived local key. "
            "Set ATLAS_SECRET_KEY in backend/.env for durable encryption."
        )
    return Fernet(_derive_fernet_key(secret))


def encrypt_text(plaintext: str) -> str:
    if not plaintext:
        return plaintext
    if plaintext.startswith(ENC_PREFIX):
        return plaintext
    token = _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")
    return f"{ENC_PREFIX}{token}"


def decrypt_text(payload: str) -> str:
    if not payload:
        return payload
    if not payload.startswith(ENC_PREFIX):
        # Legacy plaintext rows — return as-is
        return payload
    token = payload[len(ENC_PREFIX) :]
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        logger.error("Failed to decrypt secret payload (wrong ATLAS_SECRET_KEY?): %s", exc)
        raise ValueError("Cannot decrypt stored credentials — check ATLAS_SECRET_KEY") from exc


def encrypt_json(data: Dict[str, Any]) -> str:
    return encrypt_text(json.dumps(data))


def decrypt_json(payload: str) -> Dict[str, Any]:
    raw = decrypt_text(payload)
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Encrypted credential payload must be a JSON object")
    return parsed
