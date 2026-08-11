from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_user_agent
from app.core.rate_limit import limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.enums import AuditAction
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.audit import audit_service

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Hash fixo só pra gastar o mesmo tempo de Argon2id quando o usuário não existe —
# sem isso, resposta de "usuário inexistente" é mensurávelmente mais rápida que
# "senha errada", permitindo enumerar emails cadastrados por timing.
_DUMMY_PASSWORD_HASH = hash_password("timing-attack-mitigation-dummy-value")


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    email = payload.email.strip().lower()

    user = db.query(User).filter(User.email == email).first()
    password_valid = verify_password(payload.password, user.password_hash if user else _DUMMY_PASSWORD_HASH)

    if user is None or not password_valid:
        audit_service.log(
            db,
            action=AuditAction.LOGIN_FAILED,
            resource="auth",
            ip_address=ip,
            user_agent=user_agent,
            metadata={"email": email},
        )
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciais inválidas.")

    audit_service.log(
        db,
        action=AuditAction.LOGIN_SUCCESS,
        resource="auth",
        resource_id=user.id,
        user_id=user.id,
        ip_address=ip,
        user_agent=user_agent,
    )
    db.commit()

    token = create_access_token(user.id, user.role.value)
    return TokenResponse(access_token=token)
