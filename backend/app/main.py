from pathlib import Path
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.logging_config import configure_logging
from app.routers import chat, connections, documents, models, mcp, web_search, code, github, workspace, auth, admin, storage
from app.services.local_auth import get_local_auth_token, is_loopback_request

FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Atlas", version="1.0.0")

_cors_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(storage.router)
app.include_router(chat.router)
app.include_router(connections.router)
app.include_router(documents.router)
app.include_router(models.router)
app.include_router(mcp.router)
app.include_router(web_search.router)
app.include_router(code.router)
app.include_router(github.router)
app.include_router(workspace.router)


@app.on_event("startup")
def startup():
    from app.config import get_settings
    from app.storage.manager import get_storage_manager

    configure_logging(get_settings().log_level)
    # Pluggable storage: bind primary (+ optional Redis chat cache), create schema
    get_storage_manager().startup()
    token = get_local_auth_token()
    logger.info("Atlas startup complete (local auth token ready, len=%s)", len(token))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/auth/token")
def auth_token(request: Request):
    """Bootstrap local auth token for the SPA (loopback only)."""
    if not is_loopback_request(request):
        raise HTTPException(status_code=403, detail="Auth token only available on localhost")
    return {"token": get_local_auth_token(), "header": "X-Atlas-Token"}


if FRONTEND_DIST.is_dir():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/")
    def serve_spa_index():
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
