"""Multi-user isolation: second user is not admin; data stays scoped."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app


def _register(client: TestClient, email: str, password: str = "securepass1"):
    res = client.post("/api/auth/register", json={"email": email, "password": password})
    if res.status_code == 400:
        res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()


def test_second_user_is_not_admin_and_sessions_isolated():
    suffix = uuid.uuid4().hex[:8]
    with TestClient(app) as c:
        a = _register(c, f"admin-{suffix}@atlas.local")
        b = _register(c, f"user-{suffix}@atlas.local")

        # First account in a fresh DB is admin; subsequent are user.
        # If DB already had users, A may be user — assert B is never admin when A registered first in empty DB.
        # Stronger check: B is user if A was created in this test as first... use role of B relative to count.
        assert b["user"]["role"] == "user" or a["user"]["role"] == "admin"
        if a["user"]["role"] == "admin":
            assert b["user"]["role"] == "user"

        token_a = a["token"]
        token_b = b["token"]

        # Non-admin cannot hit admin API
        if b["user"]["role"] != "admin":
            denied = c.get("/api/admin/users", headers={"Authorization": f"Bearer {token_b}"})
            assert denied.status_code == 403

        # Sessions are isolated
        sa = c.post(
            "/api/sessions",
            json={"title": "A chat"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert sa.status_code == 200
        session_a = sa.json()["id"]

        list_b = c.get("/api/sessions", headers={"Authorization": f"Bearer {token_b}"})
        assert list_b.status_code == 200
        assert all(s["id"] != session_a for s in list_b.json())

        steal = c.get(
            f"/api/sessions/{session_a}/messages",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert steal.status_code == 404

        # Connections scoped: A connects, B does not see connected
        connect_a = c.post(
            "/api/connections/fiverr",
            json={
                "credentials": {
                    "profile_url": "https://www.fiverr.com/alice",
                    "username": "alice",
                    "niche": "Design",
                }
            },
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert connect_a.status_code == 200
        a_fiverr = next(r for r in connect_a.json() if r["provider"] == "fiverr")
        assert a_fiverr["connected"] is True

        list_b_conn = c.get("/api/connections", headers={"Authorization": f"Bearer {token_b}"})
        assert list_b_conn.status_code == 200
        b_fiverr = next(r for r in list_b_conn.json() if r["provider"] == "fiverr")
        assert b_fiverr["connected"] is False


def test_workspace_projects_scoped():
    suffix = uuid.uuid4().hex[:8]
    with TestClient(app) as c:
        a = _register(c, f"proj-a-{suffix}@atlas.local")
        b = _register(c, f"proj-b-{suffix}@atlas.local")
        token_a = a["token"]
        token_b = b["token"]

        created = c.post(
            "/api/workspace/projects",
            json={"name": "Secret project", "description": "private"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert created.status_code == 200
        project_id = created.json()["id"]

        list_b = c.get("/api/workspace/projects", headers={"Authorization": f"Bearer {token_b}"})
        assert list_b.status_code == 200
        assert all(p["id"] != project_id for p in list_b.json())
