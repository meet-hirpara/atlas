from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

from app.models.bot_settings import BotSettings


class SessionCreate(BaseModel):
    title: Optional[str] = "New Chat"


class SessionResponse(BaseModel):
    id: str
    title: str
    pinned: bool = False
    project_id: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_session(cls, session) -> "SessionResponse":
        return cls(
            id=session.id,
            title=session.title,
            pinned=bool(getattr(session, "pinned", 0)),
            project_id=getattr(session, "project_id", None),
            prompt_tokens=int(getattr(session, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(session, "completion_tokens", 0) or 0),
            created_at=session.created_at,
            updated_at=session.updated_at,
        )


class MessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    sources: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str = Field(min_length=1, max_length=200_000)
    sources: str = ""


class MessageBatchCreate(BaseModel):
    messages: list[MessageCreate] = Field(min_length=1, max_length=20)


class ChatRequest(BaseModel):
    message: str
    session_id: str
    settings: Optional[BotSettings] = None
    deep_research: bool = Field(default=False, alias="deepResearch")

    class Config:
        populate_by_name = True


class SessionUpdate(BaseModel):
    title: Optional[str] = None
    pinned: Optional[bool] = None
    project_id: Optional[str] = None
    clear_project: bool = False


class SessionSearchResult(BaseModel):
    session_id: str
    session_title: str
    snippet: str
    score: float
    message_role: str = "user"


class EphemeralAgentResponse(BaseModel):
    id: str
    session_id: str
    name: str
    role_prompt: str
    model_preference: str = ""
    allowed_tools: list = []
    created_at: datetime

    class Config:
        from_attributes = True


class EphemeralAgentCreate(BaseModel):
    name: str
    role_prompt: str
    model_preference: str = ""


class DiagramRequest(BaseModel):
    code: str


class DiagramResponse(BaseModel):
    svg: str


class DocumentResponse(BaseModel):
    id: str
    session_id: str
    filename: str
    file_size: int
    page_count: int
    chunk_count: int
    status: str
    error_message: str = ""
    created_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GithubRepoCreate(BaseModel):
    url: str
    token: str = ""
    branch: str = "main"


class GithubRepoResponse(BaseModel):
    id: str
    url: str
    owner: str
    name: str
    branch: str
    status: str
    error_message: str = ""
    file_count: int = 0
    chunk_count: int = 0
    created_at: datetime
    indexed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GithubGraphResponse(BaseModel):
    nodes: list
    edges: list


class GithubQueryRequest(BaseModel):
    question: str


class GithubQueryResponse(BaseModel):
    answer: str
    sources: list
    relevant: bool
    repo: str = ""

