import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import resolve_api_key
from app.core.security import InvalidTokenError, decode_access_token
from app.db.session import get_db
from app.models.api_key import ApiKey
from app.models.audit_log import AuditLog
from app.models.enums import ApiKeyScope, AuditAction, UserRole
from app.models.user import User
from app.schemas.audit import AuditLogResponse, PaginatedAuditLogs

router = APIRouter(prefix="/api/audit-logs", tags=["audit"])


def _authorize_audit_access(
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Aceita API key com scope audit:read OU usuário ADMIN autenticado via JWT."""
    if x_api_key:
        api_key = resolve_api_key(db, x_api_key)
        if not api_key.has_scope(ApiKeyScope.AUDIT_READ):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "API key sem permissão 'audit:read'.")
        return

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            payload = decode_access_token(auth_header.removeprefix("Bearer ").strip())
        except InvalidTokenError as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

        user_id = payload.get("sub")
        try:
            user = db.get(User, uuid.UUID(user_id)) if user_id else None
        except ValueError as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido.") from exc
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário não encontrado.")
        if user.role != UserRole.ADMIN:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Apenas ADMIN pode consultar auditoria.")
        return

    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Autenticação necessária (X-API-Key ou Bearer token)."
    )


@router.get("", response_model=PaginatedAuditLogs, dependencies=[Depends(_authorize_audit_access)])
def list_audit_logs(
    action: AuditAction | None = Query(default=None),
    resource: str | None = Query(default=None),
    user_id: uuid.UUID | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> PaginatedAuditLogs:
    query = db.query(AuditLog)
    if action is not None:
        query = query.filter(AuditLog.action == action)
    if resource is not None:
        query = query.filter(AuditLog.resource == resource)
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if resource_id is not None:
        query = query.filter(AuditLog.resource_id == resource_id)

    total = query.count()
    items = (
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedAuditLogs(items=items, total=total, page=page, page_size=page_size)
