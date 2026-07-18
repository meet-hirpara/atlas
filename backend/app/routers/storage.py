"""Admin storage API: status, test, apply (admin-only)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services import user_auth as auth
from app.storage.manager import DESTRUCTIVE_WARNING, get_storage_manager
from app.storage.types import (
    StorageApplyRequest,
    StorageStatusOut,
    StorageTestRequest,
    StorageTestResult,
)

router = APIRouter(prefix="/api/admin/storage", tags=["admin-storage"])


@router.get("", response_model=StorageStatusOut)
def storage_status(admin: auth.CurrentAdmin):
    return get_storage_manager().status()


@router.get("/warning")
def storage_warning(admin: auth.CurrentAdmin):
    return {"warning": DESTRUCTIVE_WARNING}


@router.post("/test", response_model=StorageTestResult)
def storage_test(body: StorageTestRequest, admin: auth.CurrentAdmin):
    return get_storage_manager().test_connection(body)


@router.post("/apply", response_model=StorageStatusOut)
def storage_apply(body: StorageApplyRequest, admin: auth.CurrentAdmin):
    try:
        return get_storage_manager().apply(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to apply storage: {exc}") from exc
