"""Storage backend types and credential shapes."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EngineType(str, Enum):
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    REDIS = "redis"


class Purpose(str, Enum):
    """Logical data domains — primary holds everything unless overridden."""

    PRIMARY = "primary"
    CHAT_CACHE = "chat_cache"


SQL_ENGINES = {EngineType.SQLITE, EngineType.POSTGRESQL, EngineType.MYSQL}
DOCUMENT_ENGINES = {EngineType.MONGODB}
CACHE_ENGINES = {EngineType.REDIS, EngineType.MONGODB}


class BackendCredentials(BaseModel):
    """Connection fields — unused keys ignored per engine."""

    path: str = ""  # sqlite file path
    host: str = "127.0.0.1"
    port: int = 0
    database: str = ""
    username: str = ""
    password: str = ""
    url: str = ""  # optional full URL override
    ssl: bool = False
    extras: Dict[str, Any] = Field(default_factory=dict)


class BackendConfig(BaseModel):
    engine: EngineType
    credentials: BackendCredentials = Field(default_factory=BackendCredentials)
    enabled: bool = True


class StorageConfig(BaseModel):
    """Active storage layout. Bootstrap file lives outside the app DB."""

    version: int = 1
    primary: BackendConfig = Field(
        default_factory=lambda: BackendConfig(
            engine=EngineType.SQLITE,
            credentials=BackendCredentials(path="./data/chatbot.db"),
        )
    )
    chat_cache: Optional[BackendConfig] = None
    # Env bootstrap wins until admin saves a config
    env_override_active: bool = False


class DataPlacement(BaseModel):
    purpose: str
    description: str
    engine: str
    location_hint: str


class StorageStatusOut(BaseModel):
    primary: Dict[str, Any]
    chat_cache: Optional[Dict[str, Any]] = None
    placement: List[DataPlacement]
    env_database_url: str
    warning: str
    engines_available: List[Dict[str, Any]]


class StorageTestRequest(BaseModel):
    engine: EngineType
    credentials: BackendCredentials = Field(default_factory=BackendCredentials)
    purpose: Purpose = Purpose.PRIMARY


class StorageTestResult(BaseModel):
    ok: bool
    engine: EngineType
    message: str
    latency_ms: Optional[float] = None


class StorageApplyRequest(BaseModel):
    primary: BackendConfig
    chat_cache: Optional[BackendConfig] = None
    confirm_destructive: bool = False
    acknowledge_data_loss: bool = False
