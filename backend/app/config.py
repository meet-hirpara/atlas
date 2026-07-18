from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    mistral_api_key: str
    mistral_model: str = "mistral-large-latest"
    database_url: str = "sqlite:///./data/chatbot.db"
    chroma_persist_dir: str = "./data/chroma"
    upload_dir: str = "./data/uploads"
    doc_chunk_size: int = 1200
    doc_chunk_overlap: int = 200
    doc_retrieval_k: int = 16
    github_repos_dir: str = "./data/github_repos"
    github_relevance_threshold: float = 0.42
    github_retrieval_k: int = 12
    tavily_api_key: str = ""
    youtube_api_key: str = ""  # optional — YouTube Data API v3; DuckDuckGo fallback if unset
    # Fernet encryption for integration/MCP secrets stored in SQLite
    atlas_secret_key: str = ""
    # Shared token for sensitive localhost APIs (/api/code/run, MCP connect)
    atlas_local_auth_token: str = ""
    # JWT signing secret for user login sessions
    atlas_jwt_secret: str = ""
    # Opt-in: allow backend /api/diagram/render to call mermaid.ink (privacy risk)
    atlas_allow_mermaid_ink: bool = False
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
