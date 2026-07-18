"""Tests for user registration, login, JWT protection, and admin panel."""

from fastapi.testclient import TestClient

from app.main import app


def test_auth_status_and_register_login_me_logout():
    with TestClient(app) as c:
        status = c.get("/api/auth/status")
        assert status.status_code == 200
        assert "has_users" in status.json()
        assert status.json()["allow_register"] is True

        email = "auth-flow@atlas.local"
        password = "securepass1"

        # Clean login attempt may fail if already registered from prior run
        reg = c.post("/api/auth/register", json={"email": email, "password": password})
        if reg.status_code == 400:
            login = c.post("/api/auth/login", json={"email": email, "password": password})
            assert login.status_code == 200, login.text
            token = login.json()["token"]
            user = login.json()["user"]
        else:
            assert reg.status_code == 200, reg.text
            token = reg.json()["token"]
            user = reg.json()["user"]
            assert user["role"] in ("admin", "user")

        me = c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["email"] == email

        # Protected route rejects missing auth
        bare = TestClient(app)
        denied = bare.get("/api/sessions")
        assert denied.status_code == 401

        # With token, sessions work
        ok = c.get("/api/sessions", headers={"Authorization": f"Bearer {token}"})
        assert ok.status_code == 200

        out = c.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert out.status_code == 200


def test_admin_list_users(client):
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    # Fixture user is first in a fresh DB or may be user — register ensures at least one admin exists
    users = client.get("/api/admin/users")
    if me.json()["role"] != "admin":
        assert users.status_code == 403
        return
    assert users.status_code == 200
    rows = users.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    assert all("email" in u and "role" in u for u in rows)

    health = client.get("/api/admin/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["users"] >= 1
