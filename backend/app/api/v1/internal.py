import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_user_agent, resolve_api_key
from app.core.security import InvalidTokenError, decode_access_token
from app.db.session import get_db
from app.models.api_key import ApiKey
from app.models.enums import ApiKeyScope, AuditAction, UserRole
from app.models.snov_account import SnovAccount
from app.models.user import User
from app.schemas.account import AccountCredentialsResponse
from app.services.audit import audit_service
from app.services.encryption import encryption_service

router = APIRouter(prefix="/api/internal/accounts", tags=["internal"])


def _authorize_credentials_access(
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> tuple[User | None, ApiKey | None]:
    """Aceita API key com scope credentials:read OU usuário ADMIN autenticado via JWT."""
    if x_api_key:
        api_key = resolve_api_key(db, x_api_key)
        if not api_key.has_scope(ApiKeyScope.CREDENTIALS_READ):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "API key sem permissão 'credentials:read'."
            )
        return None, api_key

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
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Apenas ADMIN pode visualizar credenciais diretamente."
            )
        return user, None

    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Autenticação necessária (X-API-Key ou Bearer token)."
    )


@router.get("/{account_id}/credentials", response_model=AccountCredentialsResponse)
def get_account_credentials(
    account_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    principal: tuple[User | None, ApiKey | None] = Depends(_authorize_credentials_access),
) -> AccountCredentialsResponse:
    user, api_key = principal

    account = (
        db.query(SnovAccount)
        .filter(SnovAccount.id == account_id, SnovAccount.deleted_at.is_(None))
        .first()
    )
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conta não encontrada.")

    # Descriptografia só em memória — nunca persistida em plaintext.
    response = AccountCredentialsResponse(
        account_id=account.id,
        snov_id=account.snov_id,
        snov_secret=encryption_service.decrypt(account.snov_secret_encrypted),
        snov_email=encryption_service.decrypt(account.snov_email_encrypted),
        snov_password=encryption_service.decrypt(account.snov_password_encrypted),
    )

    audit_service.log(
        db,
        action=AuditAction.CREDENTIALS_ACCESSED,
        resource="snov_account",
        resource_id=account.id,
        user_id=user.id if user else None,
        api_key_id=api_key.id if api_key else None,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        metadata={"email": account.email},
    )
    db.commit()

    return response
