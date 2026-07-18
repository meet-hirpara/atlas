"""Patch helpers for owned workspace mutations."""

from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.database import (
    Client,
    JobInboxItem,
    Project,
    Proposal,
    ScheduledResearch,
    User,
)


def _get_owned(db: Session, model, item_id: str, user: User):
    item = db.query(model).filter(model.id == item_id).first()
    if not item:
        return None
    if user.role == "admin":
        return item
    if getattr(item, "user_id", None) != user.id:
        return None
    return item


def get_owned_project(db: Session, project_id: str, user: User) -> Optional[Project]:
    return _get_owned(db, Project, project_id, user)


def get_owned_proposal(db: Session, proposal_id: str, user: User) -> Optional[Proposal]:
    return _get_owned(db, Proposal, proposal_id, user)


def get_owned_job(db: Session, job_id: str, user: User) -> Optional[JobInboxItem]:
    return _get_owned(db, JobInboxItem, job_id, user)


def get_owned_client(db: Session, client_id: str, user: User) -> Optional[Client]:
    return _get_owned(db, Client, client_id, user)


def get_owned_schedule(db: Session, schedule_id: str, user: User) -> Optional[ScheduledResearch]:
    return _get_owned(db, ScheduledResearch, schedule_id, user)


def require_owned(item: Any, detail: str = "Not found"):
    if not item:
        raise HTTPException(404, detail)
    return item
