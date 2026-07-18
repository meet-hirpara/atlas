from typing import List
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models.database import User, get_db
from app.services import mcp_connection_service
from app.services.local_auth import require_local_auth
from app.services.mcp_service import list_presets
from app.services import user_auth as auth

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/mcp",
    tags=["mcp"],
    dependencies=[Depends(auth.get_current_user)],
)


class McpServerCreate(BaseModel):
    name: str = ""
    preset: str = "custom"
    transport: str = "stdio"
    command: str = ""
    args: List[str] = Field(default_factory=list)
    url: str = ""
    env: dict = Field(default_factory=dict)


@router.get("/presets")
def get_presets():
    return {"presets": list_presets()}


@router.get("/servers")
def get_servers(
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    return {"servers": mcp_connection_service.list_servers(db, user_id=user.id)}


@router.post("/servers", dependencies=[Depends(require_local_auth)])
def add_server(
    body: McpServerCreate,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    try:
        result = mcp_connection_service.create_server(
            db, body.model_dump(), user_id=user.id
        )
        logger.info(
            "MCP server connected preset=%s name=%s updated=%s",
            body.preset,
            body.name or result.get("name"),
            result.get("updated"),
        )
        return result
    except Exception as e:
        logger.exception("MCP connect failed preset=%s: %s", body.preset, e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/servers/{server_id}/test")
def test_server(
    server_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    try:
        return mcp_connection_service.retest_server(db, server_id, user_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("MCP retest failed id=%s: %s", server_id, e)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/servers/{server_id}/tools")
def get_server_tools(
    server_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    try:
        tools = mcp_connection_service.list_server_tools(db, server_id, user_id=user.id)
        return {"tools": tools}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("MCP list tools failed id=%s: %s", server_id, e)
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/servers/{server_id}")
def patch_server(
    server_id: str,
    enabled: bool,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    result = mcp_connection_service.toggle_server(
        db, server_id, enabled, user_id=user.id
    )
    if not result:
        raise HTTPException(status_code=404, detail="Server not found")
    return result


@router.delete("/servers/{server_id}")
def remove_server(
    server_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    if not mcp_connection_service.delete_server(db, server_id, user_id=user.id):
        raise HTTPException(status_code=404, detail="Server not found")
    return {"servers": mcp_connection_service.list_servers(db, user_id=user.id)}
