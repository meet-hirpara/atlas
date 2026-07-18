from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.models.database import User, get_db, ChatSession
from app.models.workspace_schemas import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProposalCreate,
    ProposalUpdate,
    ProposalResponse,
    JobCreate,
    JobUpdate,
    JobResponse,
    ClientCreate,
    ClientUpdate,
    ClientResponse,
    AuditLogResponse,
    ArtifactResponse,
    ArtifactCreate,
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse,
    UsageResponse,
)
from app.services import workspace_service as ws
from app.services import user_auth as auth
from app.services.ownership import owned_session_or_404
from app.services import workspace_ownership as wo

router = APIRouter(
    prefix="/api/workspace",
    tags=["workspace"],
    dependencies=[Depends(auth.get_current_user)],
)


def _project_out(p) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description or "",
        "clientId": p.client_id,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


# --- Projects ---

@router.get("/projects")
def list_projects(db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    return [_project_out(p) for p in ws.list_projects(db, user_id=user.id)]


@router.post("/projects")
def create_project(body: ProjectCreate, db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    p = ws.create_project(db, body.name, body.description, body.client_id, user_id=user.id)
    return _project_out(p)


@router.patch("/projects/{project_id}")
def update_project(project_id: str, body: ProjectUpdate, db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    if not wo.get_owned_project(db, project_id, user):
        raise HTTPException(404, "Project not found")
    p = ws.update_project(db, project_id, body.name, body.description, body.client_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return _project_out(p)


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    if not wo.get_owned_project(db, project_id, user):
        raise HTTPException(404, "Project not found")
    if not ws.delete_project(db, project_id):
        raise HTTPException(404, "Project not found")
    return {"ok": True}


# --- Proposals ---

@router.get("/proposals", response_model=List[ProposalResponse])
def list_proposals(db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    return ws.list_proposals(db, user_id=user.id)


@router.post("/proposals", response_model=ProposalResponse)
def create_proposal(body: ProposalCreate, db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    return ws.create_proposal(
        db, body.title, body.content, body.platform, body.session_id, body.job_id, user_id=user.id
    )


@router.patch("/proposals/{proposal_id}", response_model=ProposalResponse)
def update_proposal(proposal_id: str, body: ProposalUpdate, db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    if not wo.get_owned_proposal(db, proposal_id, user):
        raise HTTPException(404, "Proposal not found")
    item = ws.update_proposal(db, proposal_id, body.title, body.content, body.platform)
    if not item:
        raise HTTPException(404, "Proposal not found")
    return item


@router.delete("/proposals/{proposal_id}")
def delete_proposal(proposal_id: str, db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    if not wo.get_owned_proposal(db, proposal_id, user):
        raise HTTPException(404, "Proposal not found")
    if not ws.delete_proposal(db, proposal_id):
        raise HTTPException(404, "Proposal not found")
    return {"ok": True}


# --- Jobs ---

@router.get("/jobs", response_model=List[JobResponse])
def list_jobs(db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    return ws.list_jobs(db, user_id=user.id)


@router.post("/jobs", response_model=JobResponse)
def create_job(body: JobCreate, db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    return ws.create_job(db, body.content, body.title, body.source, user_id=user.id)


@router.patch("/jobs/{job_id}", response_model=JobResponse)
def update_job(job_id: str, body: JobUpdate, db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    if not wo.get_owned_job(db, job_id, user):
        raise HTTPException(404, "Job not found")
    item = ws.update_job(
        db, job_id, status=body.status, session_id=body.session_id, rescore=body.rescore
    )
    if not item:
        raise HTTPException(404, "Job not found")
    return item


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str, db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    if not wo.get_owned_job(db, job_id, user):
        raise HTTPException(404, "Job not found")
    if not ws.delete_job(db, job_id):
        raise HTTPException(404, "Job not found")
    return {"ok": True}


# --- Clients ---

@router.get("/clients", response_model=List[ClientResponse])
def list_clients(db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    return ws.list_clients(db, user_id=user.id)


@router.post("/clients", response_model=ClientResponse)
def create_client(body: ClientCreate, db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    return ws.create_client(db, body.name, body.notes, body.rate, user_id=user.id)


@router.patch("/clients/{client_id}", response_model=ClientResponse)
def update_client(client_id: str, body: ClientUpdate, db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    if not wo.get_owned_client(db, client_id, user):
        raise HTTPException(404, "Client not found")
    item = ws.update_client(
        db, client_id, name=body.name, notes=body.notes, rate=body.rate, touch=body.touch
    )
    if not item:
        raise HTTPException(404, "Client not found")
    return item


@router.delete("/clients/{client_id}")
def delete_client(client_id: str, db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    if not wo.get_owned_client(db, client_id, user):
        raise HTTPException(404, "Client not found")
    if not ws.delete_client(db, client_id):
        raise HTTPException(404, "Client not found")
    return {"ok": True}


# --- Audit ---

@router.get("/audit", response_model=List[AuditLogResponse])
def list_audit(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    return ws.list_audit(db, limit)


@router.post("/audit")
def create_audit(
    kind: str = "system",
    action: str = "event",
    detail: str = "",
    session_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return ws.log_audit(db, kind, action, detail, session_id)


# --- Artifacts ---

@router.get("/sessions/{session_id}/artifacts", response_model=List[ArtifactResponse])
def list_artifacts(session_id: str, sync: bool = False, db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    owned_session_or_404(db, session_id, user)
    if sync:
        return ws.sync_session_artifacts(db, session_id)
    return ws.list_artifacts(db, session_id)


@router.post("/sessions/{session_id}/artifacts", response_model=ArtifactResponse)
def create_artifact(session_id: str, body: ArtifactCreate, db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    owned_session_or_404(db, session_id, user)
    return ws.save_artifact(db, session_id, body.kind, body.title, body.content, body.meta, user_id=user.id)


@router.post("/sessions/{session_id}/artifacts/sync", response_model=List[ArtifactResponse])
def sync_artifacts(session_id: str, db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    owned_session_or_404(db, session_id, user)
    return ws.sync_session_artifacts(db, session_id)


# --- Schedules ---

@router.get("/schedules", response_model=List[ScheduleResponse])
def list_schedules(db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    return ws.list_schedules(db, user_id=user.id)


@router.get("/schedules/due", response_model=List[ScheduleResponse])
def list_due_schedules(db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    return ws.due_schedules(db, user_id=user.id)


@router.post("/schedules", response_model=ScheduleResponse)
def create_schedule(body: ScheduleCreate, db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    return ws.create_schedule(db, body.topic, body.cadence, user_id=user.id)


@router.patch("/schedules/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(schedule_id: str, body: ScheduleUpdate, db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    if not wo.get_owned_schedule(db, schedule_id, user):
        raise HTTPException(404, "Schedule not found")
    item = ws.update_schedule(
        db,
        schedule_id,
        topic=body.topic,
        cadence=body.cadence,
        enabled=body.enabled,
        mark_run=body.mark_run,
        session_id=body.session_id,
    )
    if not item:
        raise HTTPException(404, "Schedule not found")
    return item


@router.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: str, db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    if not wo.get_owned_schedule(db, schedule_id, user):
        raise HTTPException(404, "Schedule not found")
    if not ws.delete_schedule(db, schedule_id):
        raise HTTPException(404, "Schedule not found")
    return {"ok": True}


# --- Usage / export / cockpit ---

@router.get("/sessions/{session_id}/usage", response_model=UsageResponse)
def session_usage(session_id: str, db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    session = owned_session_or_404(db, session_id, user)
    prompt = int(session.prompt_tokens or 0)
    completion = int(session.completion_tokens or 0)
    return UsageResponse(
        session_id=session_id,
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=prompt + completion,
    )


@router.get("/sessions/{session_id}/export")
def export_session(
    session_id: str,
    format: str = Query("markdown", pattern="^(markdown|html|md)$"),
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    owned_session_or_404(db, session_id, user)
    if format in ("markdown", "md"):
        result = ws.export_session_markdown(db, session_id)
        if not result:
            raise HTTPException(404, "Session not found")
        filename, body = result
        return PlainTextResponse(
            body,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    result = ws.export_session_html(db, session_id)
    if not result:
        raise HTTPException(404, "Session not found")
    filename, body = result
    return HTMLResponse(
        body,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/freelance/cockpit")
def freelance_cockpit(db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    return ws.freelance_cockpit_summary(db, user_id=user.id)
