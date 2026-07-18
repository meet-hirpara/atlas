from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import User, get_db
from app.models.schemas import (
    GithubGraphResponse,
    GithubQueryRequest,
    GithubQueryResponse,
    GithubRepoCreate,
    GithubRepoResponse,
)
from app.services.github_repo_service import github_repo_service
from app.services import user_auth as auth

router = APIRouter(
    prefix="/api/github",
    tags=["github"],
    dependencies=[Depends(auth.get_current_user)],
)


@router.get("/repos", response_model=List[GithubRepoResponse])
def list_repos(
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    return github_repo_service.list_repos(db, user_id=user.id)


@router.post("/repos", response_model=GithubRepoResponse)
def add_repo(
    body: GithubRepoCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    try:
        record = github_repo_service.add_repo(
            db, body.url, body.token, body.branch, user_id=user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if record.status in ("pending", "failed"):
        background_tasks.add_task(github_repo_service.index_repo, record.id, body.token)
    return record


@router.delete("/repos/{repo_id}")
def delete_repo(
    repo_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    if not github_repo_service.delete_repo(db, repo_id, user_id=user.id):
        raise HTTPException(status_code=404, detail="Repository not found")
    return {"ok": True}


@router.get("/repos/{repo_id}/graph", response_model=GithubGraphResponse)
def get_graph(
    repo_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    record = github_repo_service.get_repo(db, repo_id, user_id=user.id)
    if not record:
        raise HTTPException(status_code=404, detail="Repository not found")
    graph = github_repo_service.get_graph(db, repo_id)
    return graph


@router.post("/repos/{repo_id}/query", response_model=GithubQueryResponse)
async def query_repo(
    repo_id: str,
    body: GithubQueryRequest,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question is required")
    if not github_repo_service.get_repo(db, repo_id, user_id=user.id):
        raise HTTPException(status_code=404, detail="Repository not found")
    result = await github_repo_service.query_repo(db, repo_id, body.question.strip())
    if result.get("answer") == "Repository not found.":
        raise HTTPException(status_code=404, detail="Repository not found")
    return result
