import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_user_agent, require_roles
from app.db.session import get_db
from app.models.enums import AccountStatus, AuditAction, UserRole
from app.models.snov_account import SnovAccount
from app.models.user import User
from app.schemas.account import (
    AccountResponse,
    PaginatedAccounts,
    SnovAccountCreate,
    SnovAccountUpdate,
)
from app.services.audit import audit_service
from app.services.encryption import encryption_service

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

_READ_ROLES = (UserRole.ADMIN, UserRole.OPERATOR, UserRole.READONLY)
_WRITE_ROLES = (UserRole.ADMIN, UserRole.OPERATOR)


def _get_active_or_404(db: Session, account_id: uuid.UUID) -> SnovAccount:
    account = (
        db.query(SnovAccount)
        .filter(SnovAccount.id == account_id, SnovAccount.deleted_at.is_(None))
        .first()
    )
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conta não encontrada.")
    return account


@router.get("", response_model=PaginatedAccounts)
def list_accounts(
    q: str | None = Query(default=None, description="Busca por email da conta"),
    account_status: AccountStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*_READ_ROLES)),
) -> PaginatedAccounts:
    query = db.query(SnovAccount).filter(SnovAccount.deleted_at.is_(None))

    if account_status is not None:
        query = query.filter(SnovAccount.status == account_status)
    if q:
        query = query.filter(func.lower(SnovAccount.email).like(f"%{q.strip().lower()}%"))

    total = query.count()
    items = (
        query.order_by(SnovAccount.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedAccounts(items=items, total=total, page=page, page_size=page_size)


@router.get("/{account_id}", response_model=AccountResponse)
def get_account(
    account_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*_READ_ROLES)),
) -> SnovAccount:
    return _get_active_or_404(db, account_id)


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(
    payload: SnovAccountCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*_WRITE_ROLES)),
) -> SnovAccount:
    lookup_hash = encryption_service.hash_for_lookup(payload.snov_email)

    if db.query(SnovAccount).filter(SnovAccount.email == payload.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe uma conta com este email.")
    if db.query(SnovAccount).filter(SnovAccount.snov_email_lookup_hash == lookup_hash).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe uma conta com este snov_email.")

    account = SnovAccount(
        email=payload.email,
        snov_id=payload.snov_id,
        snov_secret_encrypted=encryption_service.encrypt(payload.snov_secret),
        snov_email_encrypted=encryption_service.encrypt(payload.snov_email),
        snov_password_encrypted=encryption_service.encrypt(payload.snov_password),
        snov_email_lookup_hash=lookup_hash,
        description=payload.description,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(account)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Conta duplicada (email ou snov_email).") from exc

    audit_service.log(
        db,
        action=AuditAction.ACCOUNT_CREATED,
        resource="snov_account",
        resource_id=account.id,
        user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        metadata={"email": account.email},
    )
    db.commit()
    db.refresh(account)
    return account


@router.patch("/{account_id}", response_model=AccountResponse)
def update_account(
    account_id: uuid.UUID,
    payload: SnovAccountUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*_WRITE_ROLES)),
) -> SnovAccount:
    account = _get_active_or_404(db, account_id)
    changed_fields: list[str] = []

    if payload.email is not None and payload.email != account.email:
        if (
            db.query(SnovAccount)
            .filter(SnovAccount.email == payload.email, SnovAccount.id != account_id)
            .first()
        ):
            raise HTTPException(status.HTTP_409_CONFLICT, "Email já em uso.")
        account.email = payload.email
        changed_fields.append("email")

    if payload.snov_id is not None:
        account.snov_id = payload.snov_id
        changed_fields.append("snov_id")

    if payload.snov_secret is not None:
        account.snov_secret_encrypted = encryption_service.encrypt(payload.snov_secret)
        changed_fields.append("snov_secret")

    if payload.snov_email is not None:
        lookup_hash = encryption_service.hash_for_lookup(payload.snov_email)
        if lookup_hash != account.snov_email_lookup_hash and (
            db.query(SnovAccount)
            .filter(
                SnovAccount.snov_email_lookup_hash == lookup_hash,
                SnovAccount.id != account_id,
            )
            .first()
        ):
            raise HTTPException(status.HTTP_409_CONFLICT, "snov_email já em uso.")
        account.snov_email_encrypted = encryption_service.encrypt(payload.snov_email)
        account.snov_email_lookup_hash = lookup_hash
        changed_fields.append("snov_email")

    if payload.snov_password is not None:
        account.snov_password_encrypted = encryption_service.encrypt(payload.snov_password)
        changed_fields.append("snov_password")

    if payload.description is not None:
        account.description = payload.description
        changed_fields.append("description")

    if not changed_fields:
        return account

    account.updated_by = user.id
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Conta duplicada (email ou snov_email).") from exc

    audit_service.log(
        db,
        action=AuditAction.ACCOUNT_UPDATED,
        resource="snov_account",
        resource_id=account.id,
        user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        metadata={"email": account.email, "changed_fields": changed_fields},
    )
    db.commit()
    db.refresh(account)
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    account_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
) -> None:
    account = _get_active_or_404(db, account_id)
    account.deleted_at = datetime.now(timezone.utc)
    account.updated_by = user.id
    db.flush()

    audit_service.log(
        db,
        action=AuditAction.ACCOUNT_DELETED,
        resource="snov_account",
        resource_id=account.id,
        user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        metadata={"email": account.email},
    )
    db.commit()


@router.patch("/{account_id}/activate", response_model=AccountResponse)
def activate_account(
    account_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*_WRITE_ROLES)),
) -> SnovAccount:
    account = _get_active_or_404(db, account_id)
    account.status = AccountStatus.ACTIVE
    account.updated_by = user.id
    db.flush()

    audit_service.log(
        db,
        action=AuditAction.ACCOUNT_ACTIVATED,
        resource="snov_account",
        resource_id=account.id,
        user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        metadata={"email": account.email},
    )
    db.commit()
    db.refresh(account)
    return account


@router.patch("/{account_id}/deactivate", response_model=AccountResponse)
def deactivate_account(
    account_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*_WRITE_ROLES)),
) -> SnovAccount:
    account = _get_active_or_404(db, account_id)
    account.status = AccountStatus.INACTIVE
    account.updated_by = user.id
    db.flush()

    audit_service.log(
        db,
        action=AuditAction.ACCOUNT_DEACTIVATED,
        resource="snov_account",
        resource_id=account.id,
        user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        metadata={"email": account.email},
    )
    db.commit()
    db.refresh(account)
    return account
