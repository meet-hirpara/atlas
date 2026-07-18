"""Security regression tests for code runner + MCP allowlist."""

import asyncio

import pytest

from app.services.code_runner_service import run_code
from app.services.mcp_service import (
    _safe_tool_name,
    mask_env_secrets,
    validate_sse_url,
    validate_stdio_launch,
)


def test_shell_disabled_by_default():
    result = asyncio.run(run_code("powershell", "Write-Host hi", allow_shell=False))
    assert result["exit_code"] == 403
    assert "disabled" in result["stderr"].lower()


def test_bash_disabled_by_default():
    result = asyncio.run(run_code("bash", "echo hi", allow_shell=False))
    assert result["exit_code"] == 403


def test_python_still_runs():
    result = asyncio.run(run_code("python", "print(2+2)", allow_shell=False))
    assert result["exit_code"] == 0
    assert "4" in result["stdout"]


def test_stdio_blocks_powershell():
    with pytest.raises(ValueError, match="not allowed"):
        validate_stdio_launch(preset="custom", command="powershell", args=["-Command", "dir"])


def test_stdio_blocks_shell_metacharacters():
    with pytest.raises(ValueError, match="Unsafe"):
        validate_stdio_launch(preset="custom", command="npx", args=["-y", "pkg; rm -rf /"])


def test_stdio_allows_npx():
    cmd, args = validate_stdio_launch(preset="custom", command="npx", args=["-y", "some-mcp"])
    assert cmd == "npx"
    assert args == ["-y", "some-mcp"]


def test_preset_forces_trusted_command():
    cmd, args = validate_stdio_launch(
        preset="upwork",
        command="powershell",
        args=["evil"],
    )
    assert cmd == "npx"
    assert "@furkankoykiran/upwork-mcp" in " ".join(args)


def test_sse_rejects_remote_hosts():
    with pytest.raises(ValueError, match="localhost"):
        validate_sse_url("http://evil.example/sse")


def test_sse_allows_localhost():
    assert validate_sse_url("http://127.0.0.1:8080/mcp").startswith("http://127.0.0.1")


def test_mask_env_secrets():
    masked = mask_env_secrets({
        "UPWORK_CLIENT_ID": "public-id",
        "UPWORK_CLIENT_SECRET": "super-secret",
    })
    assert masked["UPWORK_CLIENT_ID"] == "public-id"
    assert masked["UPWORK_CLIENT_SECRET"] == "***"


def test_mcp_tool_names_use_mcp_prefix():
    assert _safe_tool_name("Upwork", "search_jobs").startswith("mcp_")
    assert "upwork" in _safe_tool_name("Upwork", "search_jobs")
