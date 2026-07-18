from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional

from app.models.database import User, get_db
from app.models.schemas import (
    SessionCreate,
    SessionResponse,
    MessageResponse,
    MessageCreate,
    MessageBatchCreate,
    ChatRequest,
    SessionUpdate,
    SessionSearchResult,
    DiagramRequest,
    DiagramResponse,
    EphemeralAgentResponse,
    EphemeralAgentCreate,
)
from app.services.session_search_service import search_sessions
from app.services import chat_service
from app.services.diagram_service import render_mermaid_svg
from app.services.ephemeral_agent_service import (
    get_active_agent,
    dismiss_active_agent,
    create_agent_manual,
    agent_to_dict,
)
from app.services import user_auth as auth
from app.services.ownership import owned_session_or_404

router = APIRouter(
    prefix="/api",
    tags=["chat"],
    dependencies=[Depends(auth.get_current_user)],
)


def _owned_session(db: Session, session_id: str, user: User):
    return owned_session_or_404(db, session_id, user)


@router.post("/sessions", response_model=SessionResponse)
def create_session(
    body: SessionCreate = SessionCreate(),
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    session = chat_service.create_session(db, body.title or "New Chat", user_id=user.id)
    return SessionResponse.from_orm_session(session)


@router.get("/sessions", response_model=List[SessionResponse])
def list_sessions(db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    return [
        SessionResponse.from_orm_session(s)
        for s in chat_service.get_sessions(db, user_id=user.id)
    ]


@router.get("/sessions/search", response_model=List[SessionSearchResult])
def search_chat_sessions(
    q: str,
    exclude: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    hits = search_sessions(
        db, q, exclude_session_id=exclude, limit=min(limit, 20), user_id=user.id
    )
    return [
        SessionSearchResult(
            session_id=h.session_id,
            session_title=h.session_title,
            snippet=h.snippet,
            score=h.score,
            message_role=h.message_role,
        )
        for h in hits
    ]


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    session = _owned_session(db, session_id, user)
    return SessionResponse.from_orm_session(session)


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
def update_session(
    session_id: str,
    body: SessionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    from app.services import workspace_service as ws

    _owned_session(db, session_id, user)
    if body.title is not None and body.pinned is None and body.project_id is None and not body.clear_project:
        session = chat_service.update_session_title(db, session_id, body.title)
    else:
        session = ws.update_session_meta(
            db,
            session_id,
            title=body.title,
            pinned=body.pinned,
            project_id=body.project_id,
            clear_project=body.clear_project,
        )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse.from_orm_session(session)


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    _owned_session(db, session_id, user)
    if not chat_service.delete_session(db, session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True}


@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
def get_messages(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    _owned_session(db, session_id, user)
    return chat_service.get_messages(db, session_id)


@router.post("/sessions/{session_id}/messages", response_model=List[MessageResponse])
def persist_messages(
    session_id: str,
    body: MessageBatchCreate,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    """Persist connect-from-chat / stream-error messages without calling the LLM."""
    _owned_session(db, session_id, user)
    saved = []
    for item in body.messages:
        msg = chat_service.append_message(db, session_id, item.role, item.content, item.sources)
        if msg:
            saved.append(msg)
    return saved


@router.get("/sessions/{session_id}/agents")
def get_session_agent(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    _owned_session(db, session_id, user)
    agent = get_active_agent(db, session_id)
    if not agent:
        return None
    return agent_to_dict(agent)


@router.post("/sessions/{session_id}/agents", response_model=EphemeralAgentResponse)
def create_session_agent(
    session_id: str,
    body: EphemeralAgentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    _owned_session(db, session_id, user)
    agent = create_agent_manual(db, session_id, body.name, body.role_prompt, body.model_preference)
    return agent_to_dict(agent)


@router.delete("/sessions/{session_id}/agents/{agent_id}")
def delete_session_agent(
    session_id: str,
    agent_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    _owned_session(db, session_id, user)
    agent = dismiss_active_agent(db, session_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"ok": True, "name": agent.name}


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    _owned_session(db, body.session_id, user)
    return StreamingResponse(
        chat_service.stream_chat(
            db, body.session_id, body.message, body.settings, body.deep_research
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/diagram/render", response_model=DiagramResponse)
async def render_diagram(body: DiagramRequest):
    try:
        svg = await render_mermaid_svg(body.code)
        return DiagramResponse(svg=svg)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
