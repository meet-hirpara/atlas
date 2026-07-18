from datetime import datetime
from sqlalchemy import create_engine, Column, String, Text, DateTime, ForeignKey, Integer, Float, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from app.config import get_settings
import logging
import os

settings = get_settings()
os.makedirs("data", exist_ok=True)
logger = logging.getLogger(__name__)

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Runtime mode: "sql" (default) or "mongo"
_storage_mode = "sql"
_mongo_client = None
_mongo_db_name: str | None = None


def rebind_sql_engine(new_engine) -> None:
    """Hot-swap SQLAlchemy engine + session factory (primary store switch)."""
    global engine, SessionLocal, _storage_mode, _mongo_client, _mongo_db_name
    old = engine
    engine = new_engine
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    _storage_mode = "sql"
    if _mongo_client is not None:
        try:
            _mongo_client.close()
        except Exception:
            pass
    _mongo_client = None
    _mongo_db_name = None
    try:
        old.dispose()
    except Exception:
        pass
    logger.info("Rebound SQL engine → %s", engine.url.render_as_string(hide_password=True))


def rebind_mongo(client, db_name: str) -> None:
    """Switch primary store to MongoDB (ORM-shaped MongoSession)."""
    global engine, SessionLocal, _storage_mode, _mongo_client, _mongo_db_name
    _storage_mode = "mongo"
    if _mongo_client is not None and _mongo_client is not client:
        try:
            _mongo_client.close()
        except Exception:
            pass
    _mongo_client = client
    _mongo_db_name = db_name
    logger.info("Rebound primary store → MongoDB db=%s", db_name)


def storage_mode() -> str:
    return _storage_mode


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user", nullable=False)  # user | admin
    created_at = Column(DateTime, default=datetime.utcnow)


class Client(Base):
    __tablename__ = "clients"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    notes = Column(Text, default="")
    rate = Column(String, default="")
    last_contact = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    projects = relationship("Project", back_populates="client")


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    client_id = Column(String, ForeignKey("clients.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sessions = relationship("ChatSession", back_populates="project")
    client = relationship("Client", back_populates="projects")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    title = Column(String, default="New Chat")
    pinned = Column(Integer, default=0)  # 0/1 for SQLite compat
    project_id = Column(String, ForeignKey("projects.id"), nullable=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    agents = relationship("SessionAgent", back_populates="session", cascade="all, delete-orphan")
    project = relationship("Project", back_populates="sessions")


class SessionAgent(Base):
    __tablename__ = "session_agents"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("chat_sessions.id"), nullable=False)
    name = Column(String, nullable=False)
    role_prompt = Column(Text, nullable=False)
    model_preference = Column(String, default="")
    allowed_tools = Column(Text, default='["all"]')
    created_at = Column(DateTime, default=datetime.utcnow)
    session = relationship("ChatSession", back_populates="agents")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    sources = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    session = relationship("ChatSession", back_populates="messages")


class Connection(Base):
    __tablename__ = "connections"

    id = Column(String, primary_key=True)
    provider = Column(String, nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    label = Column(String, default="")
    credentials = Column(Text, nullable=False)
    connected_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class McpServer(Base):
    __tablename__ = "mcp_servers"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    preset = Column(String, default="custom")
    transport = Column(String, default="stdio")  # stdio | sse
    command = Column(String, default="")
    args = Column(Text, default="[]")
    url = Column(String, default="")
    env = Column(Text, default="{}")
    enabled = Column(Integer, default=1)
    tool_count = Column(Integer, default=0)
    tools_cache = Column(Text, default="[]")  # JSON list of {name, description, input_schema}
    connected_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class GithubRepo(Base):
    __tablename__ = "github_repos"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    url = Column(String, nullable=False)
    owner = Column(String, default="")
    name = Column(String, default="")
    branch = Column(String, default="main")
    status = Column(String, default="pending")  # pending | indexing | ready | failed
    error_message = Column(Text, default="")
    file_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    graph_json = Column(Text, default="{}")
    clone_path = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    indexed_at = Column(DateTime, nullable=True)


class UploadedDocument(Base):
    __tablename__ = "uploaded_documents"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("chat_sessions.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_size = Column(Integer, default=0)
    page_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    status = Column(String, default="pending")  # pending | processing | ready | failed
    error_message = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)


class Proposal(Base):
    __tablename__ = "proposals"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    platform = Column(String, default="")
    session_id = Column(String, nullable=True)
    job_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class JobInboxItem(Base):
    __tablename__ = "job_inbox"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    title = Column(String, default="")
    source = Column(String, default="paste")
    content = Column(Text, nullable=False)
    fit_score = Column(Float, nullable=True)
    fit_notes = Column(Text, default="")
    status = Column(String, default="new")  # new | scored | drafted | archived
    session_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLogEntry(Base):
    __tablename__ = "audit_log"

    id = Column(String, primary_key=True)
    kind = Column(String, nullable=False)  # tool | search | mcp | integration | system
    action = Column(String, nullable=False)
    detail = Column(Text, default="")
    session_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(String, nullable=False)
    kind = Column(String, nullable=False)  # diagram | code | proposal | file | research
    title = Column(String, default="")
    content = Column(Text, nullable=False)
    meta = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)


class ScheduledResearch(Base):
    __tablename__ = "scheduled_research"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    topic = Column(String, nullable=False)
    cadence = Column(String, default="weekly")  # daily | weekly | monthly
    next_run_at = Column(DateTime, nullable=True)
    last_run_at = Column(DateTime, nullable=True)
    last_result_session_id = Column(String, nullable=True)
    enabled = Column(Integer, default=1)
    reminder_note = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


_USER_ID_TABLES = (
    "chat_sessions",
    "projects",
    "clients",
    "connections",
    "mcp_servers",
    "github_repos",
    "proposals",
    "job_inbox",
    "artifacts",
    "scheduled_research",
)


def init_db(*, run_sqlite_migrations: bool | None = None):
    """Create tables. SQLite column migrations only when on a SQLite file URL."""
    if _storage_mode == "mongo":
        # Collections/indexes are created by mongo_adapter.ensure_mongo_schema
        _assign_orphans_on_startup()
        return

    Base.metadata.create_all(bind=engine)
    use_sqlite = run_sqlite_migrations
    if use_sqlite is None:
        use_sqlite = str(engine.url).startswith("sqlite")
    if use_sqlite:
        _migrate_message_sources()
        _migrate_mcp_tools_cache()
        _migrate_chat_session_columns()
        _migrate_user_id_columns()
        _migrate_connections_per_user()
    _assign_orphans_on_startup()


def _sqlite_path() -> str | None:
    url = str(engine.url) if engine is not None else settings.database_url
    if not url.startswith("sqlite"):
        return None
    db_path = url.replace("sqlite:///", "").split("?")[0]
    if not os.path.exists(db_path):
        return None
    return db_path


def _migrate_message_sources():
    """Add sources column to messages if missing (SQLite)."""
    import sqlite3

    db_path = _sqlite_path()
    if not db_path:
        return
    conn = sqlite3.connect(db_path)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
        if "sources" not in cols:
            conn.execute("ALTER TABLE messages ADD COLUMN sources TEXT DEFAULT ''")
            conn.commit()
    finally:
        conn.close()


def _migrate_mcp_tools_cache():
    """Add tools_cache column to mcp_servers if missing (SQLite)."""
    import sqlite3

    db_path = _sqlite_path()
    if not db_path:
        return
    conn = sqlite3.connect(db_path)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(mcp_servers)")}
        if "tools_cache" not in cols:
            conn.execute("ALTER TABLE mcp_servers ADD COLUMN tools_cache TEXT DEFAULT '[]'")
            conn.commit()
    finally:
        conn.close()


def _migrate_chat_session_columns():
    """Add pin/project/usage columns to chat_sessions if missing (SQLite)."""
    import sqlite3

    db_path = _sqlite_path()
    if not db_path:
        return
    conn = sqlite3.connect(db_path)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(chat_sessions)")}
        alters = []
        if "pinned" not in cols:
            alters.append("ALTER TABLE chat_sessions ADD COLUMN pinned INTEGER DEFAULT 0")
        if "project_id" not in cols:
            alters.append("ALTER TABLE chat_sessions ADD COLUMN project_id TEXT")
        if "prompt_tokens" not in cols:
            alters.append("ALTER TABLE chat_sessions ADD COLUMN prompt_tokens INTEGER DEFAULT 0")
        if "completion_tokens" not in cols:
            alters.append("ALTER TABLE chat_sessions ADD COLUMN completion_tokens INTEGER DEFAULT 0")
        for stmt in alters:
            conn.execute(stmt)
        if alters:
            conn.commit()
    finally:
        conn.close()


def _migrate_user_id_columns():
    """Add nullable user_id columns for soft multi-user ownership (SQLite)."""
    import sqlite3

    db_path = _sqlite_path()
    if not db_path:
        return
    conn = sqlite3.connect(db_path)
    try:
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        for table in _USER_ID_TABLES:
            if table not in tables:
                continue
            cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            if "user_id" not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id TEXT")
        conn.commit()
    finally:
        conn.close()


def _migrate_connections_per_user():
    """Recreate connections with id PK so each user can own the same provider."""
    import sqlite3
    import uuid

    db_path = _sqlite_path()
    if not db_path:
        return
    conn = sqlite3.connect(db_path)
    try:
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        if "connections" not in tables:
            return
        cols = {row[1] for row in conn.execute("PRAGMA table_info(connections)")}
        if "id" in cols:
            return
        conn.execute(
            """
            CREATE TABLE connections_new (
                id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                user_id TEXT,
                label TEXT DEFAULT '',
                credentials TEXT NOT NULL,
                connected_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_conn_user_provider "
            "ON connections_new(user_id, provider)"
        )
        rows = conn.execute(
            "SELECT provider, user_id, label, credentials, connected_at, updated_at "
            "FROM connections"
        ).fetchall()
        for provider, user_id, label, credentials, connected_at, updated_at in rows:
            conn.execute(
                "INSERT INTO connections_new "
                "(id, provider, user_id, label, credentials, connected_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    provider,
                    user_id,
                    label or "",
                    credentials,
                    connected_at,
                    updated_at,
                ),
            )
        conn.execute("DROP TABLE connections")
        conn.execute("ALTER TABLE connections_new RENAME TO connections")
        conn.commit()
        logger.info("Migrated connections table to per-user ownership")
    finally:
        conn.close()


def assign_orphaned_data_to_user(db: Session, user_id: str) -> int:
    """Assign rows with NULL user_id to the given user. Returns total rows updated."""
    updated = 0
    models = (
        ChatSession,
        Project,
        Client,
        Connection,
        McpServer,
        GithubRepo,
        Proposal,
        JobInboxItem,
        Artifact,
        ScheduledResearch,
    )
    for model in models:
        q = db.query(model).filter(model.user_id.is_(None))
        count = q.count()
        if count:
            q.update({model.user_id: user_id}, synchronize_session=False)
            updated += count
    if updated:
        db.commit()
        logger.info("Assigned %s orphaned rows to user %s", updated, user_id)
    return updated


def _session_factory():
    """Return a DB session for the active primary (SQL or Mongo)."""
    if _storage_mode == "mongo":
        from app.storage.mongo_adapter import MongoSession

        if _mongo_client is None or not _mongo_db_name:
            raise RuntimeError("Mongo primary selected but client is not bound")
        return MongoSession(_mongo_client, _mongo_db_name)
    return SessionLocal()


# Alias for background jobs that previously used SessionLocal()
open_db = _session_factory


def _assign_orphans_on_startup():
    """If an admin already exists, attach any leftover orphaned rows."""
    db = _session_factory()
    try:
        admin = (
            db.query(User)
            .filter(User.role == "admin")
            .order_by(User.created_at.asc())
            .first()
        )
        if admin:
            assign_orphaned_data_to_user(db, admin.id)
    finally:
        db.close()


def get_db():
    db = _session_factory()
    try:
        yield db
    finally:
        db.close()
