import uuid
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import InvalidTokenError, decode_access_token, hash_api_key
from app.db.session import get_db
from app.models.api_key import ApiKey
from app.models.enums import ApiKeyScope, ApiKeyStatus, UserRole
from app.models.user import User


def get_client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def get_user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token de autenticação ausente.")

    token = auth_header.removeprefix("Bearer ").strip()
    try:
        payload = decode_access_token(token)
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    user_id = payload.get("sub")
    try:
        user = db.get(User, uuid.UUID(user_id)) if user_id else None
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido.") from exc
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário não encontrado.")
    return user


def require_roles(*roles: UserRole):
    def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Permissão insuficiente.")
        return user

    return _dependency


def resolve_api_key(db: Session, raw_key: str | None) -> ApiKey:
    if not raw_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key ausente.")

    key_hash = hash_api_key(raw_key)
    api_key = db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
    if api_key is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key inválida.")
    if api_key.status != ApiKeyStatus.ACTIVE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "API key revogada.")
    if api_key.expires_at is not None and api_key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "API key expirada.")

    api_key.last_used_at = datetime.now(timezone.utc)
    db.flush()
    return api_key


def get_api_key(
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> ApiKey:
    return resolve_api_key(db, x_api_key)


def require_scope(scope: ApiKeyScope):
    def _dependency(api_key: ApiKey = Depends(get_api_key)) -> ApiKey:
        if not api_key.has_scope(scope):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, f"API key sem permissão '{scope.value}'."
            )
        return api_key

    return _dependency
