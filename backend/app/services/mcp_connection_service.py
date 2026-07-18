import json
import logging
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.database import McpServer
from app.services.mcp_service import (
    MCP_PRESETS,
    MASKED_SECRET,
    _list_tools_async,
    _run_async,
    _server_cfg_for_launch,
    _server_to_dict,
    test_mcp_server,
    validate_sse_url,
    validate_stdio_launch,
)
from app.services.secret_store import decrypt_json, encrypt_json

logger = logging.getLogger(__name__)


def _load_env(row: McpServer) -> dict:
    raw = row.env or "{}"
    try:
        return decrypt_json(raw)
    except ValueError:
        # Legacy plaintext JSON
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Corrupt MCP env for server=%s", row.id)
            return {}
    except Exception as exc:
        logger.error("Failed to decrypt MCP env for %s: %s", row.id, exc)
        try:
            return json.loads(raw) if not str(raw).startswith("enc:v1:") else {}
        except json.JSONDecodeError:
            return {}


def _store_env(env: dict) -> str:
    return encrypt_json(env or {})


def list_servers(db: Session, user_id: Optional[str] = None) -> List[dict]:
    q = db.query(McpServer).order_by(McpServer.connected_at.desc())
    if user_id:
        q = q.filter(McpServer.user_id == user_id)
    rows = q.all()
    return [_server_to_dict(r, mask_secrets=True) for r in rows]


def get_server(
    db: Session, server_id: str, user_id: Optional[str] = None
) -> Optional[McpServer]:
    q = db.query(McpServer).filter(McpServer.id == server_id)
    if user_id:
        q = q.filter(McpServer.user_id == user_id)
    return q.first()


def _merge_env(existing: dict, incoming: dict) -> dict:
    """Merge env updates; keep existing secrets when client sends masked placeholders."""
    merged = dict(existing or {})
    for key, value in (incoming or {}).items():
        if value is None:
            continue
        if value == MASKED_SECRET and key in merged:
            continue
        if value == "" and key in merged and str(key).upper().find("SECRET") >= 0:
            continue
        merged[key] = value
    return merged


def _find_upsert_target(
    db: Session, preset: str, name: str, user_id: Optional[str] = None
) -> Optional[McpServer]:
    """Prefer updating an existing row for the same non-custom preset (or exact name)."""
    if preset and preset != "custom":
        q = (
            db.query(McpServer)
            .filter(McpServer.preset == preset)
            .order_by(McpServer.connected_at.desc())
        )
        if user_id:
            q = q.filter(McpServer.user_id == user_id)
        row = q.first()
        if row:
            return row
    if name:
        q = db.query(McpServer).filter(McpServer.name == name)
        if user_id:
            q = q.filter(McpServer.user_id == user_id)
        return q.first()
    return None


def create_server(db: Session, data: dict, user_id: Optional[str] = None) -> dict:
    preset = data.get("preset", "custom")
    preset_cfg = MCP_PRESETS.get(preset, MCP_PRESETS["custom"])

    transport = data.get("transport") or preset_cfg.get("transport", "stdio")
    command = data.get("command", preset_cfg.get("command", ""))
    args = data.get("args", preset_cfg.get("args", []))
    url = data.get("url", preset_cfg.get("url", ""))
    name = data.get("name") or preset_cfg.get("name", "MCP Server")

    if not isinstance(args, list):
        args = json.loads(args or "[]")

    if transport == "stdio":
        command, args = validate_stdio_launch(preset=preset, command=command, args=args)
    else:
        url = validate_sse_url(url, preset=preset)

    preset_env = preset_cfg.get("default_env") or {}
    user_env = data.get("env") or {}

    existing = _find_upsert_target(db, preset, name, user_id=user_id)
    if existing:
        existing_env = _load_env(existing)
        merged_env = _merge_env({**preset_env, **existing_env}, user_env)
    else:
        merged_env = {**preset_env, **user_env}

    server_cfg = {
        "preset": preset,
        "transport": transport,
        "command": command,
        "args": args,
        "url": url,
        "env": merged_env,
    }
    tools = _run_async(_list_tools_async(server_cfg))
    tool_count = len(tools)
    msg = f"Connected — {tool_count} tools available"

    if existing:
        existing.name = name
        existing.preset = preset
        existing.transport = transport
        existing.command = command
        existing.args = json.dumps(args)
        existing.url = url
        existing.env = _store_env(merged_env)
        existing.enabled = 1
        existing.tool_count = tool_count
        existing.tools_cache = json.dumps(tools)
        existing.updated_at = datetime.utcnow()
        if user_id and not existing.user_id:
            existing.user_id = user_id
        db.commit()
        db.refresh(existing)
        logger.info("Updated MCP server id=%s preset=%s tools=%s", existing.id, preset, tool_count)
        result = _server_to_dict(existing, mask_secrets=True)
        result["test_message"] = msg
        result["updated"] = True
        return result

    row = McpServer(
        id=str(uuid.uuid4()),
        user_id=user_id,
        name=name,
        preset=preset,
        transport=transport,
        command=command,
        args=json.dumps(args),
        url=url,
        env=_store_env(merged_env),
        enabled=1,
        tool_count=tool_count,
        tools_cache=json.dumps(tools),
        connected_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    result = _server_to_dict(row, mask_secrets=True)
    result["test_message"] = msg
    result["updated"] = False
    return result


def delete_server(
    db: Session, server_id: str, user_id: Optional[str] = None
) -> bool:
    row = get_server(db, server_id, user_id=user_id)
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def toggle_server(
    db: Session, server_id: str, enabled: bool, user_id: Optional[str] = None
) -> Optional[dict]:
    row = get_server(db, server_id, user_id=user_id)
    if not row:
        return None
    row.enabled = 1 if enabled else 0
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _server_to_dict(row, mask_secrets=True)


def retest_server(
    db: Session, server_id: str, user_id: Optional[str] = None
) -> dict:
    row = get_server(db, server_id, user_id=user_id)
    if not row:
        raise ValueError("Server not found")
    server_cfg = _server_cfg_for_launch(row)
    msg, tool_count = test_mcp_server(server_cfg)
    tools = _run_async(_list_tools_async(server_cfg))
    row.tool_count = tool_count
    row.tools_cache = json.dumps(tools)
    row.updated_at = datetime.utcnow()
    db.commit()
    return {"message": msg, "tool_count": tool_count}


def list_server_tools(
    db: Session, server_id: str, user_id: Optional[str] = None
) -> List[dict]:
    row = get_server(db, server_id, user_id=user_id)
    if not row:
        raise ValueError("Server not found")
    cached = []
    try:
        cached = json.loads(row.tools_cache or "[]")
    except (json.JSONDecodeError, TypeError):
        cached = []
    if cached:
        return [
            {"name": t["name"], "description": t.get("description") or t["name"]}
            for t in cached
        ]
    server_cfg = _server_cfg_for_launch(row)
    tools = _run_async(_list_tools_async(server_cfg))
    row.tools_cache = json.dumps(tools)
    row.tool_count = len(tools)
    db.commit()
    return [
        {
            "name": t["name"],
            "description": t.get("description") or t["name"],
        }
        for t in tools
    ]
