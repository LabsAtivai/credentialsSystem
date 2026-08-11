import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_user_agent, require_roles
from app.core.security import generate_api_key
from app.db.session import get_db
from app.models.api_key import ApiKey
from app.models.enums import ApiKeyStatus, AuditAction, UserRole
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreatedResponse, ApiKeyResponse
from app.services.audit import audit_service

router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])


@router.get("", response_model=list[ApiKeyResponse])
def list_api_keys(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
) -> list[ApiKey]:
    return db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()


@router.post("", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_api_key(
    payload: ApiKeyCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
) -> ApiKeyCreatedResponse:
    full_key, prefix, key_hash = generate_api_key()

    api_key = ApiKey(
        name=payload.name,
        key_hash=key_hash,
        prefix=prefix,
        scopes=[scope.value for scope in payload.scopes],
        expires_at=payload.expires_at,
        created_by=user.id,
    )
    db.add(api_key)
    db.flush()

    audit_service.log(
        db,
        action=AuditAction.API_KEY_CREATED,
        resource="api_key",
        resource_id=api_key.id,
        user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        metadata={"name": api_key.name, "scopes": api_key.scopes, "prefix": api_key.prefix},
    )
    db.commit()
    db.refresh(api_key)

    # Única vez em que a chave completa é exposta — o cliente deve guardá-la agora.
    return ApiKeyCreatedResponse(
        id=api_key.id,
        name=api_key.name,
        prefix=api_key.prefix,
        scopes=api_key.scopes,
        api_key=full_key,
    )


@router.patch("/{api_key_id}/revoke", response_model=ApiKeyResponse)
def revoke_api_key(
    api_key_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
) -> ApiKey:
    api_key = db.query(ApiKey).filter(ApiKey.id == api_key_id).first()
    if api_key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key não encontrada.")

    api_key.status = ApiKeyStatus.REVOKED
    db.flush()

    audit_service.log(
        db,
        action=AuditAction.API_KEY_REVOKED,
        resource="api_key",
        resource_id=api_key.id,
        user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        metadata={"name": api_key.name, "prefix": api_key.prefix},
    )
    db.commit()
    db.refresh(api_key)
    return api_key
