"""MCP (Model Context Protocol) client — connect Blender, Unity, and custom servers."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model
from sqlalchemy.orm import Session

from app.models.database import McpServer

logger = logging.getLogger(__name__)

# Only these executables may be spawned for stdio MCP (basename match).
ALLOWED_STDIO_COMMANDS = frozenset({"uvx", "npx", "node", "npm", "python", "python3", "py"})
# Reject shell wrappers / interpreters that enable arbitrary RCE.
BLOCKED_STDIO_COMMANDS = frozenset({
    "bash", "sh", "zsh", "fish", "cmd", "cmd.exe", "powershell", "powershell.exe",
    "pwsh", "pwsh.exe", "cscript", "wscript", "mshta", "curl", "wget",
})
SECRET_ENV_KEYS = frozenset({
    "UPWORK_CLIENT_SECRET", "CLIENT_SECRET", "API_SECRET", "API_KEY",
    "TOKEN", "ACCESS_TOKEN", "PASSWORD", "SECRET",
})
MASKED_SECRET = "***"

# ── Presets for 3D software ───────────────────────────────────────────────────

MCP_PRESETS: Dict[str, dict] = {
    "blender": {
        "id": "blender",
        "name": "Blender",
        "description": "Create & edit 3D objects, materials, and scenes in Blender",
        "color": "#E87D0D",
        "transport": "stdio",
        "command": "uvx",
        "args": ["blender-mcp"],
        "url": "",
        "setup_steps": [
            "Install uv: pip install uv (needed for uvx command)",
            "Install Blender MCP addon and open Blender",
            "In Blender press N → MCP tab → click Start Server",
            "Click Quick connect below (uses: uvx blender-mcp)",
        ],
    },
    "blender_sse": {
        "id": "blender_sse",
        "name": "Blender (HTTP/SSE)",
        "description": "Blender MCP via HTTP endpoint",
        "color": "#E87D0D",
        "transport": "sse",
        "command": "",
        "args": [],
        "url": "http://127.0.0.1:8765/sse",
        "setup_steps": [
            "Start Blender with MCP addon and HTTP server enabled",
            "Copy the SSE URL from the Blender MCP panel (often http://127.0.0.1:8765/sse)",
            "Paste or confirm the URL in Configure & connect, then connect",
        ],
    },
    "unity": {
        "id": "unity",
        "name": "Unity Editor",
        "description": "Create GameObjects, scenes, and scripts in Unity",
        "color": "#222C37",
        "transport": "sse",
        "command": "",
        "args": [],
        "url": "http://127.0.0.1:8080/mcp",
        "setup_steps": [
            "In Unity: Window → Package Manager → add MCP for Unity (CoplayDev/unity-mcp)",
            "Open Window → MCP for Unity → click Start Server",
            "Keep Unity Editor open, then click Quick connect (default URL http://127.0.0.1:8080/mcp)",
        ],
    },
    "unity_stdio": {
        "id": "unity_stdio",
        "name": "Unity (stdio bridge)",
        "description": "Unity via Coplay MCP stdio launcher",
        "color": "#222C37",
        "transport": "stdio",
        "command": "uvx",
        "args": ["mcp-remote", "http://127.0.0.1:8080/mcp"],
        "url": "",
        "setup_steps": [
            "Start Unity MCP HTTP server in the Editor first (see Unity preset steps)",
            "Quick connect uses uvx mcp-remote to bridge stdio → Unity HTTP",
            "Requires uv installed: pip install uv",
        ],
    },
    "upwork": {
        "id": "upwork",
        "name": "Upwork",
        "description": "Search jobs, manage proposals, and track contracts via Upwork GraphQL API",
        "color": "#14A800",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@furkankoykiran/upwork-mcp"],
        "url": "",
        "env_fields": [
            {
                "key": "UPWORK_CLIENT_ID",
                "label": "OAuth Client ID",
                "secret": False,
                "required": True,
                "hint": "From Upwork Developer Portal → API Keys",
            },
            {
                "key": "UPWORK_CLIENT_SECRET",
                "label": "OAuth Client Secret",
                "secret": True,
                "required": True,
                "hint": "Keep private — stored locally with this MCP connection",
            },
        ],
        "setup_steps": [
            "Create an API app at https://www.upwork.com/developer/keys/apply",
            "Enter Client ID and Client Secret below, then Connect",
            "After connect, run once in a terminal: npx -y @furkankoykiran/upwork-mcp auth",
            "Complete Upwork OAuth in your browser to authorize Atlas",
            "Use chat to search jobs, list proposals, or draft with live Upwork data",
        ],
        "notes": (
            "Community MCP server (@furkankoykiran/upwork-mcp) — not maintained by Upwork. "
            "Upwork documents a PUBLIC_MCP API scope (Upwork Everywhere) but does not publish "
            "a first-party MCP package; this preset uses the well-maintained community server."
        ),
    },
    "custom": {
        "id": "custom",
        "name": "Custom MCP Server",
        "description": "Any MCP-compatible server (stdio or SSE)",
        "color": "#8B5CF6",
        "transport": "stdio",
        "command": "",
        "args": [],
        "url": "",
        "setup_steps": [
            "Choose stdio (local command) or SSE (HTTP URL) as transport",
            "Enter command + args for stdio, e.g. uvx your-mcp-package",
            "Or enter the SSE URL for remote/HTTP MCP servers",
            "Click Connect & discover tools to test and save",
        ],
    },
}


def list_presets() -> List[dict]:
    return list(MCP_PRESETS.values())


def _command_basename(command: str) -> str:
    name = (command or "").strip().replace("\\", "/").split("/")[-1]
    return name.lower()


def _is_secret_env_key(key: str) -> bool:
    upper = key.upper()
    if upper in SECRET_ENV_KEYS:
        return True
    return any(token in upper for token in ("SECRET", "PASSWORD", "TOKEN", "API_KEY"))


def mask_env_secrets(env: dict, *, reveal_non_secret: bool = True) -> dict:
    """Return env suitable for API responses — secrets never leave as plaintext."""
    if not isinstance(env, dict):
        return {}
    out: dict = {}
    for key, value in env.items():
        if _is_secret_env_key(str(key)):
            out[key] = MASKED_SECRET if value else ""
        elif reveal_non_secret:
            out[key] = value
        else:
            out[key] = value
    return out


def validate_stdio_launch(
    *,
    preset: str,
    command: str,
    args: list,
) -> Tuple[str, list]:
    """Validate / normalize stdio command+args. Raises ValueError on reject."""
    preset_cfg = MCP_PRESETS.get(preset) or {}
    cmd = (command or "").strip()
    arg_list = list(args) if isinstance(args, list) else []

    # Trusted presets: force the known command/args (env may still vary).
    if preset and preset != "custom" and preset in MCP_PRESETS:
        forced_cmd = (preset_cfg.get("command") or "").strip()
        forced_args = list(preset_cfg.get("args") or [])
        if forced_cmd:
            return forced_cmd, forced_args

    basename = _command_basename(cmd)
    if not basename:
        raise ValueError("Command is required for stdio transport")
    if basename in BLOCKED_STDIO_COMMANDS:
        raise ValueError(f"Command '{basename}' is not allowed for MCP stdio")
    if basename not in ALLOWED_STDIO_COMMANDS:
        raise ValueError(
            f"Command '{basename}' is not on the MCP allowlist. "
            f"Allowed: {', '.join(sorted(ALLOWED_STDIO_COMMANDS))}"
        )
    if any(not isinstance(a, str) for a in arg_list):
        raise ValueError("MCP args must be strings")
    # Block shell metacharacters / chaining inside args
    dangerous = re.compile(r"[;&|`$<>]|&&|\|\|")
    for a in arg_list:
        if dangerous.search(a):
            raise ValueError(f"Unsafe character in MCP arg: {a!r}")
    return cmd, arg_list


def validate_sse_url(url: str, *, preset: str = "custom") -> str:
    cleaned = (url or "").strip()
    if not cleaned:
        raise ValueError("SSE URL is required")
    parsed = urlparse(cleaned)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("SSE URL must be http or https")
    host = (parsed.hostname or "").lower()
    # Presets target local editors; custom may use localhost too.
    allowed_hosts = {"127.0.0.1", "localhost", "::1"}
    if host not in allowed_hosts:
        raise ValueError(
            "SSE MCP URL host must be localhost / 127.0.0.1 "
            "(remote MCP hosts are not allowed)"
        )
    return cleaned


def _safe_tool_name(server_name: str, tool_name: str) -> str:
    """Namespace MCP tools as mcp_* to avoid colliding with integration tools."""
    base = re.sub(r"[^a-zA-Z0-9_]", "_", f"mcp_{server_name}_{tool_name}".lower())
    return base[:64]


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result(timeout=120)


async def _with_mcp_session(server: dict, fn):
    transport = server.get("transport", "stdio")
    if transport == "sse":
        from mcp.client.sse import sse_client

        url = validate_sse_url(server.get("url", ""), preset=server.get("preset", "custom"))
        async with sse_client(url) as (read, write):
            from mcp import ClientSession

            async with ClientSession(read, write) as session:
                await session.initialize()
                return await fn(session)
    else:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        command, args = validate_stdio_launch(
            preset=server.get("preset", "custom"),
            command=server.get("command", ""),
            args=server.get("args") or [],
        )
        env = server.get("env") or {}
        # Never pass masked placeholders back into the process env
        clean_env = {
            k: v for k, v in env.items()
            if v and v != MASKED_SECRET
        }
        merged_env = {**os.environ, **clean_env} if clean_env else None
        params = StdioServerParameters(command=command, args=args, env=merged_env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await fn(session)


def _decrypt_env_blob(raw: str) -> dict:
    from app.services.secret_store import decrypt_json

    raw = raw or "{}"
    try:
        return decrypt_json(raw)
    except Exception:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Could not parse MCP env blob")
            return {}


def _server_to_dict(row: McpServer, *, mask_secrets: bool = True) -> dict:
    env = _decrypt_env_blob(row.env or "{}")
    tools_cache = []
    try:
        tools_cache = json.loads(getattr(row, "tools_cache", None) or "[]")
    except (json.JSONDecodeError, TypeError):
        tools_cache = []
    return {
        "id": row.id,
        "name": row.name,
        "preset": row.preset,
        "transport": row.transport,
        "command": row.command or "",
        "args": json.loads(row.args or "[]"),
        "url": row.url or "",
        "env": mask_env_secrets(env) if mask_secrets else env,
        "enabled": bool(row.enabled),
        "tool_count": row.tool_count or 0,
        "connected_at": row.connected_at.isoformat() if row.connected_at else None,
        "tools_cache": tools_cache if not mask_secrets else [],
        "has_cached_tools": bool(tools_cache),
    }


def _server_cfg_for_launch(row: McpServer) -> dict:
    """Internal config with real secrets for spawning MCP processes."""
    return _server_to_dict(row, mask_secrets=False)


def _schema_to_model(tool_name: str, schema: Optional[dict]) -> type[BaseModel]:
    if not schema or not isinstance(schema, dict):
        class EmptyArgs(BaseModel):
            pass
        return EmptyArgs

    props = schema.get("properties") or {}
    if not props:
        class EmptyArgs(BaseModel):
            pass
        return EmptyArgs

    required = set(schema.get("required") or [])
    fields: Dict[str, Any] = {}
    for key, spec in props.items():
        if not isinstance(spec, dict):
            spec = {}
        t = spec.get("type", "string")
        py_type = str
        if t == "integer":
            py_type = int
        elif t == "number":
            py_type = float
        elif t == "boolean":
            py_type = bool
        elif t == "array":
            py_type = list
        elif t == "object":
            py_type = dict
        desc = spec.get("description", "")
        if key in required:
            fields[key] = (py_type, Field(description=desc))
        else:
            fields[key] = (Optional[py_type], Field(default=None, description=desc))

    safe = re.sub(r"[^a-zA-Z0-9_]", "_", tool_name)[:40] or "Args"
    return create_model(f"Mcp{safe}", **fields)


async def _list_tools_async(server: dict) -> List[dict]:
    async def _list(session):
        result = await session.list_tools()
        return [
            {
                "name": t.name,
                "description": t.description or t.name,
                "input_schema": t.inputSchema if hasattr(t, "inputSchema") else {},
            }
            for t in result.tools
        ]

    return await _with_mcp_session(server, _list)


async def _call_tool_async(server: dict, tool_name: str, arguments: dict) -> str:
    async def _call(session):
        result = await session.call_tool(tool_name, arguments=arguments)
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
            else:
                parts.append(str(block))
        return "\n".join(parts) if parts else "Tool completed successfully."

    return await _with_mcp_session(server, _call)


def test_mcp_server(server: dict) -> Tuple[str, int]:
    tools = _run_async(_list_tools_async(server))
    return f"Connected — {len(tools)} tools available", len(tools)


def call_mcp_tool(server: dict, tool_name: str, arguments: dict) -> str:
    try:
        return _run_async(_call_tool_async(server, tool_name, arguments))
    except Exception as e:
        return f"MCP tool error: {e}"


def build_mcp_tools(db: Session, user_id: Optional[str] = None) -> List[StructuredTool]:
    """Build LangChain tools from cached MCP schemas (no per-turn respawn)."""
    q = db.query(McpServer).filter(McpServer.enabled == 1)
    if user_id:
        q = q.filter(McpServer.user_id == user_id)
    rows = q.all()
    tools: List[StructuredTool] = []
    offline: List[str] = []

    for row in rows:
        server = _server_cfg_for_launch(row)
        cached = server.get("tools_cache") or []
        if not cached:
            # One-time discovery if cache empty (e.g. legacy rows)
            try:
                cached = _run_async(_list_tools_async(server))
                row.tools_cache = json.dumps(cached)
                row.tool_count = len(cached)
                db.commit()
            except Exception as exc:
                logger.warning("MCP tool discovery failed for %s: %s", row.name, exc)
                offline.append(row.name)
                continue

        for mt in cached:
            tname = mt["name"]
            desc = f"[MCP:{row.name}] {mt.get('description') or tname}"
            schema_model = _schema_to_model(tname, mt.get("input_schema"))
            srv = dict(server)
            tn = tname

            def _make_invoke(_srv, _tn, _row_name):
                def _invoke(**kwargs):
                    clean = {k: v for k, v in kwargs.items() if v is not None}
                    try:
                        return call_mcp_tool(_srv, _tn, clean)
                    except Exception as exc:
                        return f"MCP tool error ({_row_name}/{_tn}): {exc}"
                return _invoke

            tools.append(
                StructuredTool.from_function(
                    func=_make_invoke(srv, tn, row.name),
                    name=_safe_tool_name(row.name, tname),
                    description=desc,
                    args_schema=schema_model,
                )
            )

    if offline:
        # Stash for prompt builder via module attribute (read in build_mcp_prompt)
        build_mcp_tools._last_offline = offline  # type: ignore[attr-defined]
    else:
        build_mcp_tools._last_offline = []  # type: ignore[attr-defined]

    return tools


def get_mcp_offline_servers() -> List[str]:
    return list(getattr(build_mcp_tools, "_last_offline", []) or [])


def build_mcp_prompt(db: Session, user_id: Optional[str] = None) -> str:
    q = db.query(McpServer).filter(McpServer.enabled == 1)
    if user_id:
        q = q.filter(McpServer.user_id == user_id)
    rows = q.all()
    if not rows:
        return ""
    lines = [f"- **{r.name}** ({r.tool_count} MCP tools, namespaced `mcp_*`)" for r in rows]
    offline = get_mcp_offline_servers()
    offline_note = ""
    if offline:
        offline_note = (
            "\n⚠️ These MCP servers failed schema discovery and have no tools this turn: "
            + ", ".join(offline)
            + ". Ask the user to retest in Settings → MCP."
        )
    return f"""
## Connected MCP servers
{chr(10).join(lines)}
{offline_note}

When the user asks to create 3D objects, modify scenes, run Blender/Unity commands, or automate the editor:
- Use the MCP tools prefixed with `mcp_` + server name (e.g. mcp_blender_*, mcp_unity_*).
- Confirm what you created or changed after each tool call.
- If Blender/Unity is not running or MCP server is offline, tell the user to start it in Settings → MCP.

When the user asks about Upwork jobs, proposals, contracts, or profile (and an Upwork MCP server is connected):
- Prefer live `mcp_upwork_*` MCP tools over profile-only `upwork_*` integration tools.
- For submit/update/withdraw proposal mutations, prefer dry_run=true first unless the user explicitly confirms.
- If tools fail with auth errors, tell the user to run: npx -y @furkankoykiran/upwork-mcp auth
"""
