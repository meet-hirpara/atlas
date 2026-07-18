"""Shared pytest fixtures — auto-auth for API smoke tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MISTRAL_API_KEY", "test-key-for-pytest")
os.environ.setdefault("ATLAS_JWT_SECRET", "pytest-jwt-secret-key")
# Keep storage bootstrap out of the developer data/ tree during tests
_test_cfg = Path(__file__).resolve().parent / "_tmp_storage_config.json"
os.environ.setdefault("ATLAS_STORAGE_CONFIG", str(_test_cfg))

from app.main import app
from app.services import user_auth as auth


@pytest.fixture(scope="session", autouse=True)
def _init_database():
    from app.storage.config_store import set_config_path
    from app.storage.manager import get_storage_manager

    set_config_path(_test_cfg)
    # Reset manager so tests don't inherit a prior apply mid-session
    mgr = get_storage_manager()
    mgr._started = False
    mgr.startup()


@pytest.fixture
def client():
    """Authenticated TestClient. First registration becomes admin."""
    with TestClient(app) as c:
        email = f"test-{os.getpid()}@atlas.local"
        password = "testpass123"
        # Try login first in case user already exists from a prior test module
        login = c.post("/api/auth/login", json={"email": email, "password": password})
        if login.status_code != 200:
            reg = c.post(
                "/api/auth/register",
                json={"email": email, "password": password},
            )
            assert reg.status_code == 200, reg.text
            token = reg.json()["token"]
        else:
            token = login.json()["token"]
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c


@pytest.fixture
def admin_headers(client):
    return {"Authorization": client.headers["Authorization"]}
