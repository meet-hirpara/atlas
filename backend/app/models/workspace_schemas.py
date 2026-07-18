from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    client_id: Optional[str] = Field(default=None, alias="clientId")

    class Config:
        populate_by_name = True


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    client_id: Optional[str] = Field(default=None, alias="clientId")

    class Config:
        populate_by_name = True


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    client_id: Optional[str] = Field(default=None, alias="clientId")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


class ProposalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    platform: str = ""
    session_id: Optional[str] = Field(default=None, alias="sessionId")
    job_id: Optional[str] = Field(default=None, alias="jobId")

    class Config:
        populate_by_name = True


class ProposalUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    platform: Optional[str] = None


class ProposalResponse(BaseModel):
    id: str
    title: str
    content: str
    platform: str = ""
    session_id: Optional[str] = None
    job_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class JobCreate(BaseModel):
    content: str = Field(min_length=1)
    title: str = ""
    source: str = "paste"


class JobUpdate(BaseModel):
    status: Optional[str] = None
    session_id: Optional[str] = Field(default=None, alias="sessionId")
    rescore: bool = False

    class Config:
        populate_by_name = True


class JobResponse(BaseModel):
    id: str
    title: str
    source: str = "paste"
    content: str
    fit_score: Optional[float] = None
    fit_notes: str = ""
    status: str = "new"
    session_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    notes: str = ""
    rate: str = ""


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    notes: Optional[str] = None
    rate: Optional[str] = None
    touch: bool = False


class ClientResponse(BaseModel):
    id: str
    name: str
    notes: str = ""
    rate: str = ""
    last_contact: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    id: str
    kind: str
    action: str
    detail: str = ""
    session_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ArtifactResponse(BaseModel):
    id: str
    session_id: str
    kind: str
    title: str
    content: str
    meta: str = "{}"
    created_at: datetime

    class Config:
        from_attributes = True


class ArtifactCreate(BaseModel):
    kind: str
    title: str = ""
    content: str
    meta: Optional[dict[str, Any]] = None


class ScheduleCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    cadence: str = "weekly"


class ScheduleUpdate(BaseModel):
    topic: Optional[str] = None
    cadence: Optional[str] = None
    enabled: Optional[bool] = None
    mark_run: bool = Field(default=False, alias="markRun")
    session_id: Optional[str] = Field(default=None, alias="sessionId")

    class Config:
        populate_by_name = True


class ScheduleResponse(BaseModel):
    id: str
    topic: str
    cadence: str
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    last_result_session_id: Optional[str] = None
    enabled: int = 1
    reminder_note: str = ""
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UsageResponse(BaseModel):
    session_id: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
