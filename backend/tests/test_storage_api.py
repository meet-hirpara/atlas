"""Admin storage API: status, test, apply; non-admin denied."""

from __future__ import annotations

import os
import uuid

from fastapi.testclient import TestClient

os.environ.setdefault("MISTRAL_API_KEY", "test-key-for-pytest")
os.environ.setdefault("ATLAS_JWT_SECRET", "pytest-jwt-secret-key")

from app.main import app
from app.storage.types import EngineType


def _register(client: TestClient, email: str, password: str = "testpass123"):
    res = client.post("/api/auth/register", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()


def test_storage_status_admin_only(client):
    st = client.get("/api/admin/storage")
    me = client.get("/api/auth/me")
    if me.json().get("role") != "admin":
        assert st.status_code == 403
        return
    assert st.status_code == 200, st.text
    data = st.json()
    assert "primary" in data
    assert data["primary"]["engine"] in ("sqlite", "postgresql", "mysql", "mongodb")
    warn = data["warning"].lower()
    assert "warning" in data and ("fresh" in warn or "admins" in warn or "migrat" in warn)
    assert isinstance(data["placement"], list)
    assert len(data["placement"]) >= 1


def test_storage_denied_for_non_admin():
    with TestClient(app) as c:
        suffix = uuid.uuid4().hex[:8]
        a = _register(c, f"admin-storage-{suffix}@atlas.local")
        b = _register(c, f"user-storage-{suffix}@atlas.local")
        if b["user"]["role"] == "admin":
            return
        denied = c.get(
            "/api/admin/storage",
            headers={"Authorization": f"Bearer {b['token']}"},
        )
        assert denied.status_code == 403
        if a["user"]["role"] == "admin":
            ok = c.get(
                "/api/admin/storage",
                headers={"Authorization": f"Bearer {a['token']}"},
            )
            assert ok.status_code == 200


def test_storage_test_sqlite(client):
    me = client.get("/api/auth/me")
    if me.json().get("role") != "admin":
        return
    res = client.post(
        "/api/admin/storage/test",
        json={
            "engine": EngineType.SQLITE.value,
            "credentials": {"path": "./data/chatbot.db"},
            "purpose": "primary",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["engine"] == "sqlite"


def test_storage_apply_requires_ack(client):
    me = client.get("/api/auth/me")
    if me.json().get("role") != "admin":
        return
    res = client.post(
        "/api/admin/storage/apply",
        json={
            "primary": {
                "engine": "sqlite",
                "credentials": {"path": "./data/chatbot.db"},
                "enabled": True,
            },
            "chat_cache": None,
            "confirm_destructive": False,
            "acknowledge_data_loss": False,
        },
    )
    assert res.status_code == 400
    detail = res.json()["detail"].lower()
    assert "destructive" in detail or "acknowledge" in detail


def test_storage_apply_sqlite_and_restore(client, tmp_path):
    """Apply a fresh sqlite file, then restore default so other tests keep working."""
    me = client.get("/api/auth/me")
    if me.json().get("role") != "admin":
        return

    db_path = str(tmp_path / "atlas-storage-test.db")
    res = client.post(
        "/api/admin/storage/apply",
        json={
            "primary": {
                "engine": "sqlite",
                "credentials": {"path": db_path},
                "enabled": True,
            },
            "chat_cache": None,
            "confirm_destructive": True,
            "acknowledge_data_loss": True,
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["primary"]["engine"] == "sqlite"

    # Restore shared default SQLite (still admin JWT may not resolve on empty DB)
    restore = client.post(
        "/api/admin/storage/apply",
        json={
            "primary": {
                "engine": "sqlite",
                "credentials": {"path": "./data/chatbot.db"},
                "enabled": True,
            },
            "chat_cache": None,
            "confirm_destructive": True,
            "acknowledge_data_loss": True,
        },
    )
    # After first apply, /me user is gone → apply may 401. Rebind via manager directly.
    if restore.status_code != 200:
        from app.storage.manager import get_storage_manager
        from app.storage.types import BackendConfig, BackendCredentials, EngineType, StorageApplyRequest

        get_storage_manager().apply(
            StorageApplyRequest(
                primary=BackendConfig(
                    engine=EngineType.SQLITE,
                    credentials=BackendCredentials(path="./data/chatbot.db"),
                ),
                chat_cache=None,
                confirm_destructive=True,
                acknowledge_data_loss=True,
            )
        )
