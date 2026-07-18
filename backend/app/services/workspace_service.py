"""Workspace domain: projects, proposals, jobs, CRM, audit, artifacts, schedules."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.database import (
    Artifact,
    AuditLogEntry,
    ChatSession,
    Client,
    JobInboxItem,
    Message,
    Project,
    Proposal,
    ScheduledResearch,
)


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def add_usage(db: Session, session_id: str, prompt_text: str, completion_text: str) -> None:
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        return
    session.prompt_tokens = int(session.prompt_tokens or 0) + estimate_tokens(prompt_text)
    session.completion_tokens = int(session.completion_tokens or 0) + estimate_tokens(completion_text)
    db.commit()


def log_audit(
    db: Session,
    kind: str,
    action: str,
    detail: str = "",
    session_id: Optional[str] = None,
) -> AuditLogEntry:
    entry = AuditLogEntry(
        id=str(uuid.uuid4()),
        kind=kind,
        action=action,
        detail=(detail or "")[:4000],
        session_id=session_id,
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_audit(db: Session, limit: int = 100) -> list[AuditLogEntry]:
    return (
        db.query(AuditLogEntry)
        .order_by(AuditLogEntry.created_at.desc())
        .limit(min(limit, 500))
        .all()
    )


# --- Projects ---

def list_projects(db: Session, user_id: Optional[str] = None) -> list[Project]:
    q = db.query(Project).order_by(Project.updated_at.desc())
    if user_id:
        q = q.filter(Project.user_id == user_id)
    return q.all()


def create_project(db: Session, name: str, description: str = "", client_id: Optional[str] = None, user_id: Optional[str] = None) -> Project:
    project = Project(
        id=str(uuid.uuid4()),
        user_id=user_id,
        name=name.strip() or "Untitled project",
        description=description or "",
        client_id=client_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def update_project(
    db: Session,
    project_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    client_id: Optional[str] = None,
) -> Optional[Project]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return None
    if name is not None:
        project.name = name.strip() or project.name
    if description is not None:
        project.description = description
    if client_id is not None:
        project.client_id = client_id or None
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project_id: str) -> bool:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return False
    for session in db.query(ChatSession).filter(ChatSession.project_id == project_id).all():
        session.project_id = None
    db.delete(project)
    db.commit()
    return True


# --- Sessions pin / project ---

def update_session_meta(
    db: Session,
    session_id: str,
    *,
    title: Optional[str] = None,
    pinned: Optional[bool] = None,
    project_id: Optional[str] = None,
    clear_project: bool = False,
) -> Optional[ChatSession]:
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        return None
    if title is not None:
        session.title = title.strip() or session.title
    if pinned is not None:
        session.pinned = 1 if pinned else 0
    if clear_project:
        session.project_id = None
    elif project_id is not None:
        session.project_id = project_id or None
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return session


def get_sessions_ordered(db: Session, user_id: Optional[str] = None) -> list[ChatSession]:
    q = db.query(ChatSession)
    if user_id:
        q = q.filter(ChatSession.user_id == user_id)
    return q.order_by(ChatSession.pinned.desc(), ChatSession.updated_at.desc()).all()


# --- Proposals ---

def list_proposals(db: Session, user_id: Optional[str] = None) -> list[Proposal]:
    q = db.query(Proposal).order_by(Proposal.updated_at.desc())
    if user_id:
        q = q.filter(Proposal.user_id == user_id)
    return q.all()


def create_proposal(
    db: Session,
    title: str,
    content: str,
    platform: str = "",
    session_id: Optional[str] = None,
    job_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Proposal:
    item = Proposal(
        id=str(uuid.uuid4()),
        user_id=user_id,
        title=(title.strip() or "Untitled proposal")[:200],
        content=content,
        platform=platform or "",
        session_id=session_id,
        job_id=job_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_proposal(
    db: Session,
    proposal_id: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    platform: Optional[str] = None,
) -> Optional[Proposal]:
    item = db.query(Proposal).filter(Proposal.id == proposal_id).first()
    if not item:
        return None
    if title is not None:
        item.title = title.strip() or item.title
    if content is not None:
        item.content = content
    if platform is not None:
        item.platform = platform
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return item


def delete_proposal(db: Session, proposal_id: str) -> bool:
    item = db.query(Proposal).filter(Proposal.id == proposal_id).first()
    if not item:
        return False
    db.delete(item)
    db.commit()
    return True


# --- Job inbox ---

_SKILL_HINTS = (
    "python", "javascript", "typescript", "react", "node", "fastapi", "django",
    "api", "backend", "frontend", "full stack", "fullstack", "ml", "ai",
    "design", "figma", "wordpress", "shopify", "seo", "content", "writing",
    "mobile", "ios", "android", "devops", "aws", "docker",
)


def score_job_fit(content: str, profile_keywords: Optional[list[str]] = None) -> tuple[float, str]:
    text = (content or "").lower()
    keywords = [k.lower() for k in (profile_keywords or list(_SKILL_HINTS))]
    hits = [k for k in keywords if k in text]
    unique = list(dict.fromkeys(hits))
    base = min(95.0, 35.0 + len(unique) * 8.0)
    budget = 0.0
    if re.search(r"\$\s*\d+|budget|hourly|fixed.?price", text):
        budget = 5.0
    score = round(min(99.0, base + budget), 1)
    if unique:
        notes = f"Matched skills: {', '.join(unique[:8])}."
    else:
        notes = "Few skill matches found — review manually before bidding."
    if budget:
        notes += " Budget signals present."
    return score, notes


def list_jobs(db: Session, user_id: Optional[str] = None) -> list[JobInboxItem]:
    q = db.query(JobInboxItem).order_by(JobInboxItem.updated_at.desc())
    if user_id:
        q = q.filter(JobInboxItem.user_id == user_id)
    return q.all()


def create_job(db: Session, content: str, title: str = "", source: str = "paste", user_id: Optional[str] = None) -> JobInboxItem:
    body = content.strip()
    derived = title.strip()
    if not derived:
        first = body.split("\n", 1)[0].strip()
        derived = (first[:80] + "…") if len(first) > 80 else (first or "Untitled job")
    score, notes = score_job_fit(body)
    item = JobInboxItem(
        id=str(uuid.uuid4()),
        user_id=user_id,
        title=derived,
        source=source or "paste",
        content=body,
        fit_score=score,
        fit_notes=notes,
        status="scored",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_job(
    db: Session,
    job_id: str,
    *,
    status: Optional[str] = None,
    session_id: Optional[str] = None,
    rescore: bool = False,
) -> Optional[JobInboxItem]:
    item = db.query(JobInboxItem).filter(JobInboxItem.id == job_id).first()
    if not item:
        return None
    if rescore:
        score, notes = score_job_fit(item.content)
        item.fit_score = score
        item.fit_notes = notes
        item.status = "scored"
    if status is not None:
        item.status = status
    if session_id is not None:
        item.session_id = session_id
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return item


def delete_job(db: Session, job_id: str) -> bool:
    item = db.query(JobInboxItem).filter(JobInboxItem.id == job_id).first()
    if not item:
        return False
    db.delete(item)
    db.commit()
    return True


# --- Clients (CRM lite) ---

def list_clients(db: Session, user_id: Optional[str] = None) -> list[Client]:
    q = db.query(Client).order_by(Client.updated_at.desc())
    if user_id:
        q = q.filter(Client.user_id == user_id)
    return q.all()


def create_client(
    db: Session,
    name: str,
    notes: str = "",
    rate: str = "",
    last_contact: Optional[datetime] = None,
    user_id: Optional[str] = None,
) -> Client:
    client = Client(
        id=str(uuid.uuid4()),
        user_id=user_id,
        name=name.strip() or "Untitled client",
        notes=notes or "",
        rate=rate or "",
        last_contact=last_contact,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def update_client(
    db: Session,
    client_id: str,
    *,
    name: Optional[str] = None,
    notes: Optional[str] = None,
    rate: Optional[str] = None,
    last_contact: Optional[datetime] = None,
    touch: bool = False,
) -> Optional[Client]:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        return None
    if name is not None:
        client.name = name.strip() or client.name
    if notes is not None:
        client.notes = notes
    if rate is not None:
        client.rate = rate
    if last_contact is not None:
        client.last_contact = last_contact
    if touch:
        client.last_contact = datetime.utcnow()
    client.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(client)
    return client


def delete_client(db: Session, client_id: str) -> bool:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        return False
    for project in db.query(Project).filter(Project.client_id == client_id).all():
        project.client_id = None
    db.delete(client)
    db.commit()
    return True


# --- Artifacts ---

_CODE_FENCE = re.compile(r"```(\w+)?\n([\s\S]*?)```", re.MULTILINE)
_MERMAID = re.compile(r"```mermaid\n([\s\S]*?)```", re.IGNORECASE)
_PATH_FENCE = re.compile(r"```([^\n`]+)\n([\s\S]*?)```")


def extract_artifacts_from_messages(messages: list[Message], session_id: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for msg in messages:
        if msg.role != "assistant":
            continue
        content = msg.content or ""
        for m in _MERMAID.finditer(content):
            code = m.group(1).strip()
            found.append({
                "kind": "diagram",
                "title": "Mermaid diagram",
                "content": code,
                "meta": {},
            })
        for m in _PATH_FENCE.finditer(content):
            lang_or_path = (m.group(1) or "").strip()
            body = m.group(2)
            if lang_or_path.lower() == "mermaid":
                continue
            if "/" in lang_or_path or "\\" in lang_or_path or "." in lang_or_path:
                found.append({
                    "kind": "file",
                    "title": lang_or_path.split("/")[-1].split("\\")[-1],
                    "content": body,
                    "meta": {"path": lang_or_path},
                })
            elif lang_or_path in ("python", "js", "ts", "tsx", "jsx", "json", "html", "css", "sql", "bash", "sh"):
                found.append({
                    "kind": "code",
                    "title": f"{lang_or_path} snippet",
                    "content": body,
                    "meta": {"language": lang_or_path},
                })
        lower = content.lower()
        if "proposal" in lower and len(content) > 200:
            # Heuristic: proposal-like long assistant replies
            if any(w in lower for w in ("dear", "i would", "my experience", "cover letter", "hire me")):
                found.append({
                    "kind": "proposal",
                    "title": "Proposal draft",
                    "content": content[:8000],
                    "meta": {},
                })
        if "research report" in lower or content.startswith("# ") and "sources" in lower:
            found.append({
                "kind": "research",
                "title": "Research report",
                "content": content[:12000],
                "meta": {},
            })
    # Deduplicate by kind+title+content hash
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in found:
        key = f"{item['kind']}|{item['title']}|{item['content'][:120]}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def sync_session_artifacts(db: Session, session_id: str) -> list[Artifact]:
    messages = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    extracted = extract_artifacts_from_messages(messages, session_id)
    db.query(Artifact).filter(Artifact.session_id == session_id).delete()
    saved: list[Artifact] = []
    for item in extracted:
        art = Artifact(
            id=str(uuid.uuid4()),
            session_id=session_id,
            kind=item["kind"],
            title=item["title"],
            content=item["content"],
            meta=json.dumps(item.get("meta") or {}),
            created_at=datetime.utcnow(),
        )
        db.add(art)
        saved.append(art)
    db.commit()
    for art in saved:
        db.refresh(art)
    return saved


def list_artifacts(db: Session, session_id: str) -> list[Artifact]:
    return (
        db.query(Artifact)
        .filter(Artifact.session_id == session_id)
        .order_by(Artifact.created_at.desc())
        .all()
    )


def save_artifact(
    db: Session,
    session_id: str,
    kind: str,
    title: str,
    content: str,
    meta: Optional[dict] = None,
    user_id: Optional[str] = None,
) -> Artifact:
    art = Artifact(
        id=str(uuid.uuid4()),
        user_id=user_id,
        session_id=session_id,
        kind=kind,
        title=title or kind,
        content=content,
        meta=json.dumps(meta or {}),
        created_at=datetime.utcnow(),
    )
    db.add(art)
    db.commit()
    db.refresh(art)
    return art


# --- Scheduled research ---

def _next_run(cadence: str, from_dt: Optional[datetime] = None) -> datetime:
    now = from_dt or datetime.utcnow()
    if cadence == "daily":
        return now + timedelta(days=1)
    if cadence == "monthly":
        return now + timedelta(days=30)
    return now + timedelta(days=7)


def list_schedules(db: Session, user_id: Optional[str] = None) -> list[ScheduledResearch]:
    q = db.query(ScheduledResearch).order_by(ScheduledResearch.next_run_at.asc())
    if user_id:
        q = q.filter(ScheduledResearch.user_id == user_id)
    return q.all()


def create_schedule(db: Session, topic: str, cadence: str = "weekly", user_id: Optional[str] = None) -> ScheduledResearch:
    item = ScheduledResearch(
        id=str(uuid.uuid4()),
        user_id=user_id,
        topic=topic.strip(),
        cadence=cadence if cadence in ("daily", "weekly", "monthly") else "weekly",
        next_run_at=_next_run(cadence),
        enabled=1,
        reminder_note=f"Due: research “{topic.strip()[:60]}”",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_schedule(
    db: Session,
    schedule_id: str,
    *,
    topic: Optional[str] = None,
    cadence: Optional[str] = None,
    enabled: Optional[bool] = None,
    mark_run: bool = False,
    session_id: Optional[str] = None,
) -> Optional[ScheduledResearch]:
    item = db.query(ScheduledResearch).filter(ScheduledResearch.id == schedule_id).first()
    if not item:
        return None
    if topic is not None:
        item.topic = topic.strip() or item.topic
        item.reminder_note = f"Due: research “{item.topic[:60]}”"
    if cadence is not None and cadence in ("daily", "weekly", "monthly"):
        item.cadence = cadence
    if enabled is not None:
        item.enabled = 1 if enabled else 0
    if mark_run:
        item.last_run_at = datetime.utcnow()
        item.last_result_session_id = session_id
        item.next_run_at = _next_run(item.cadence)
        item.reminder_note = ""
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return item


def delete_schedule(db: Session, schedule_id: str) -> bool:
    item = db.query(ScheduledResearch).filter(ScheduledResearch.id == schedule_id).first()
    if not item:
        return False
    db.delete(item)
    db.commit()
    return True


def due_schedules(db: Session, user_id: Optional[str] = None) -> list[ScheduledResearch]:
    now = datetime.utcnow()
    q = (
        db.query(ScheduledResearch)
        .filter(ScheduledResearch.enabled == 1)
        .filter(ScheduledResearch.next_run_at != None)  # noqa: E711
        .filter(ScheduledResearch.next_run_at <= now)
        .order_by(ScheduledResearch.next_run_at.asc())
    )
    if user_id:
        q = q.filter(ScheduledResearch.user_id == user_id)
    return q.all()


# --- Export ---

def export_session_markdown(db: Session, session_id: str) -> Optional[tuple[str, str]]:
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        return None
    messages = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    lines = [
        f"# {session.title}",
        "",
        f"_Exported from Atlas · {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
    ]
    for msg in messages:
        role = "You" if msg.role == "user" else "Atlas"
        lines.append(f"## {role}")
        lines.append("")
        lines.append(msg.content or "")
        lines.append("")
    usage = (
        f"_Approx. usage: {int(session.prompt_tokens or 0)} prompt + "
        f"{int(session.completion_tokens or 0)} completion tokens_"
    )
    lines.append("---")
    lines.append(usage)
    filename = re.sub(r"[^\w\-]+", "_", session.title.strip())[:60] or "chat"
    return f"{filename}.md", "\n".join(lines)


def export_session_html(db: Session, session_id: str) -> Optional[tuple[str, str]]:
    result = export_session_markdown(db, session_id)
    if not result:
        return None
    filename_md, md = result
    # Escape minimal HTML; keep preformatted markdown body for print-to-PDF
    escaped = (
        md.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>{filename_md.replace('.md', '')}</title>
<style>
  body {{ font-family: Georgia, serif; max-width: 720px; margin: 2rem auto; padding: 0 1rem; line-height: 1.55; color: #1a1a1a; }}
  pre {{ white-space: pre-wrap; font-family: inherit; }}
  @media print {{ body {{ margin: 0; }} }}
</style>
</head>
<body>
<pre>{escaped}</pre>
<script>/* Open this file and use Print → Save as PDF */</script>
</body>
</html>"""
    return filename_md.replace(".md", ".html"), html


def freelance_cockpit_summary(db: Session, user_id: Optional[str] = None) -> dict[str, Any]:
    from app.models.database import Connection

    cq = db.query(Connection)
    if user_id:
        cq = cq.filter(Connection.user_id == user_id)
    connections = cq.all()
    freelance_ids = {
        "upwork", "fiverr", "freelancer", "toptal", "peopleperhour", "guru",
        "malt", "contra", "99designs", "designcrowd", "workana", "truelancer", "bark",
    }
    connected = [c.provider for c in connections if c.provider in freelance_ids]
    jobs = list_jobs(db, user_id=user_id)
    proposals = list_proposals(db, user_id=user_id)
    return {
        "connected_platforms": connected,
        "job_count": len(jobs),
        "open_jobs": len([j for j in jobs if j.status in ("new", "scored")]),
        "proposal_count": len(proposals),
        "recent_jobs": [
            {
                "id": j.id,
                "title": j.title,
                "fit_score": j.fit_score,
                "status": j.status,
            }
            for j in jobs[:5]
        ],
        "recent_proposals": [
            {"id": p.id, "title": p.title, "platform": p.platform}
            for p in proposals[:5]
        ],
    }
