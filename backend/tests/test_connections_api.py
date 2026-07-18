"""Tests for integrations catalog and connection API."""

from app.integrations.registry import PROVIDER_IDS
from app.services.mcp_service import MCP_PRESETS

CLASSIC_PROVIDER_IDS = (
    "slack",
    "gmail",
    "github",
    "notion",
    "jira",
    "stripe",
    "postgres",
    "webhook",
)


def test_list_providers_returns_catalog(client):
    res = client.get("/api/connections/providers")
    assert res.status_code == 200
    data = res.json()
    assert "providers" in data
    providers = data["providers"]
    assert len(providers) == len(PROVIDER_IDS)

    ids = {p["id"] for p in providers}
    for expected in CLASSIC_PROVIDER_IDS + ("upwork", "fiverr", "freelancer", "99designs"):
        assert expected in ids

    freelance = [p for p in providers if p["category"] == "freelance"]
    assert len(freelance) >= 10
    upwork = next(p for p in freelance if p["id"] == "upwork")
    assert upwork["capabilities"]
    assert upwork["fields"]

    slack = next(p for p in providers if p["id"] == "slack")
    assert slack["category"] == "messaging"
    assert slack["status"] == "available"


def test_list_connections_returns_all_providers(client):
    res = client.get("/api/connections")
    assert res.status_code == 200
    rows = res.json()
    assert isinstance(rows, list)
    assert len(rows) == len(PROVIDER_IDS)
    assert all("provider" in r and "connected" in r for r in rows)
    assert {r["provider"] for r in rows} == set(PROVIDER_IDS)


def test_mcp_presets_endpoint(client):
    res = client.get("/api/mcp/presets")
    assert res.status_code == 200
    presets = res.json()["presets"]
    assert len(presets) == len(MCP_PRESETS)
    ids = {p["id"] for p in presets}
    assert ids == set(MCP_PRESETS.keys())
    assert "blender" in ids
    assert "upwork" in ids
    assert "custom" in ids


def test_freelance_connect_and_disconnect(client):
    body = {
        "credentials": {
            "profile_url": "https://www.fiverr.com/testuser",
            "username": "testuser",
            "niche": "Logo design",
        }
    }
    connect = client.post("/api/connections/fiverr", json=body)
    assert connect.status_code == 200
    rows = connect.json()
    fiverr = next(r for r in rows if r["provider"] == "fiverr")
    assert fiverr["connected"] is True
    assert fiverr["label"]

    disconnect = client.delete("/api/connections/fiverr")
    assert disconnect.status_code == 200
    fiverr = next(r for r in disconnect.json() if r["provider"] == "fiverr")
    assert fiverr["connected"] is False
