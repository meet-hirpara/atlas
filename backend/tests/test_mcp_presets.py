"""Tests for MCP preset configuration."""

from app.services.mcp_service import MCP_PRESETS, list_presets


def test_list_presets_includes_upwork():
    presets = list_presets()
    ids = {p["id"] for p in presets}
    assert "upwork" in ids


def test_upwork_preset_uses_community_npm_server():
    upwork = MCP_PRESETS["upwork"]
    assert upwork["transport"] == "stdio"
    assert upwork["command"] == "npx"
    assert any("@furkankoykiran/upwork-mcp" in a for a in upwork["args"])


def test_upwork_preset_requires_oauth_env_fields():
    upwork = MCP_PRESETS["upwork"]
    keys = {f["key"] for f in upwork["env_fields"]}
    assert keys == {"UPWORK_CLIENT_ID", "UPWORK_CLIENT_SECRET"}
    assert upwork.get("notes")


def test_upwork_preset_has_setup_steps():
    upwork = MCP_PRESETS["upwork"]
    assert len(upwork["setup_steps"]) >= 4
    assert any("developer" in s.lower() for s in upwork["setup_steps"])
