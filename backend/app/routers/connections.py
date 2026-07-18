from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.integrations.registry import get_provider, list_provider_catalog, normalize_credentials
from app.models.connection_schemas import ConnectionStatus, ConnectRequest
from app.models.database import User, get_db
from app.services import connection_service
from app.services import user_auth as auth

router = APIRouter(
    prefix="/api/connections",
    tags=["connections"],
    dependencies=[Depends(auth.get_current_user)],
)


@router.get("/providers")
def list_providers():
    return {"providers": list_provider_catalog()}


@router.get("", response_model=list[ConnectionStatus])
def list_connections(
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    return connection_service.list_connections(db, user_id=user.id)


@router.post("/{provider}", response_model=list[ConnectionStatus])
def connect_provider(
    provider: str,
    body: ConnectRequest,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    provider_def = get_provider(provider)
    if not provider_def:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")

    try:
        creds = normalize_credentials(provider, body.credentials)
        label = provider_def.build_label(creds)
        provider_def.validate(creds)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"{provider_def.name} connection failed: {e}")

    return connection_service.save_connection(db, provider, creds, label, user_id=user.id)


@router.delete("/{provider}", response_model=list[ConnectionStatus])
def disconnect(
    provider: str,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    if not get_provider(provider):
        raise HTTPException(status_code=404, detail="Unknown provider")
    connection_service.delete_connection(db, provider, user_id=user.id)
    return connection_service.list_connections(db, user_id=user.id)
