import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.models.enums import AccountStatus


class SnovAccountCreate(BaseModel):
    email: EmailStr
    snov_id: str
    snov_secret: str
    snov_email: EmailStr
    snov_password: str
    description: str | None = None

    @field_validator("email", "snov_email")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("snov_id", "snov_secret", "snov_password")
    @classmethod
    def _strip_and_require(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("campo obrigatório não pode ser vazio")
        return v


class SnovAccountUpdate(BaseModel):
    email: EmailStr | None = None
    snov_id: str | None = None
    snov_secret: str | None = None
    snov_email: EmailStr | None = None
    snov_password: str | None = None
    description: str | None = None

    @field_validator("email", "snov_email")
    @classmethod
    def _normalize_email(cls, v: str | None) -> str | None:
        return v.strip().lower() if v is not None else v

    @field_validator("snov_id", "snov_secret", "snov_password")
    @classmethod
    def _strip_and_require(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("campo não pode ser vazio")
        return v


# Dados administrativos — NUNCA incluir snov_secret/snov_email/snov_password.
class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    status: AccountStatus
    description: str | None
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PaginatedAccounts(BaseModel):
    items: list[AccountResponse]
    total: int
    page: int
    page_size: int


# Somente para consumidores autorizados via /api/internal/accounts/{id}/credentials.
class AccountCredentialsResponse(BaseModel):
    account_id: uuid.UUID
    snov_id: str
    snov_secret: str
    snov_email: str
    snov_password: str
