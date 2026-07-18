"""Tests for at-rest encryption, local auth, and postgres hardening."""

import os

import pytest
from fastapi import HTTPException
from starlette.requests import Request

# Ensure settings can load before importing app modules that touch DB
os.environ.setdefault("MISTRAL_API_KEY", "test-key-for-pytest")


def test_secret_store_roundtrip(monkeypatch):
    monkeypatch.setenv("ATLAS_SECRET_KEY", "unit-test-secret-key-abc123")
    from app.config import get_settings
    from app.services import secret_store

    get_settings.cache_clear()
    secret_store._fernet.cache_clear()

    payload = {"token": "super-secret", "email": "a@b.com"}
    enc = secret_store.encrypt_json(payload)
    assert enc.startswith("enc:v1:")
    assert "super-secret" not in enc
    assert secret_store.decrypt_json(enc) == payload

    # Idempotent encrypt
    assert secret_store.encrypt_text(enc) == enc

    get_settings.cache_clear()
    secret_store._fernet.cache_clear()


def test_legacy_plaintext_decrypt():
    from app.services.secret_store import decrypt_json

    assert decrypt_json('{"a": 1}') == {"a": 1}


def test_postgres_readonly_guard():
    from app.integrations.actions import _is_readonly_select

    assert _is_readonly_select("SELECT 1")
    assert _is_readonly_select("WITH x AS (SELECT 1) SELECT * FROM x")
    assert not _is_readonly_select("INSERT INTO t VALUES (1)")
    assert not _is_readonly_select("SELECT 1; DROP TABLE users")
    assert not _is_readonly_select("UPDATE t SET a=1")
    assert not _is_readonly_select("SELECT * FROM t; DELETE FROM t")


def test_require_confirm_blocks():
    from app.integrations.actions import require_confirm, slack_send

    assert require_confirm(False, "sending") is not None
    assert require_confirm(True, "sending") is None
    # Without real token, confirmation gate still fires first
    result = slack_send({"bot_token": "x"}, "#general", "hi", confirm=False)
    assert "Confirmation required" in result


def test_local_auth_rejects_missing_token(monkeypatch):
    monkeypatch.setenv("ATLAS_LOCAL_AUTH_TOKEN", "fixed-test-token")
    from app.services import local_auth

    local_auth._cached_token = None

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/code/run",
        "raw_path": b"/api/code/run",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 8000),
    }
    request = Request(scope)
    with pytest.raises(HTTPException) as exc:
        local_auth.require_local_auth(request, x_atlas_token=None)
    assert exc.value.status_code == 401

    # Valid token passes
    local_auth.require_local_auth(request, x_atlas_token="fixed-test-token")
    local_auth._cached_token = None
