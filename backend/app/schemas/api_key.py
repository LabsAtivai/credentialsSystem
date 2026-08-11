import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.enums import ApiKeyScope, ApiKeyStatus


class ApiKeyCreate(BaseModel):
    name: str
    scopes: list[ApiKeyScope]
    expires_at: datetime | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("nome não pode ser vazio")
        return v

    @field_validator("scopes")
    @classmethod
    def _require_at_least_one_scope(cls, v: list[ApiKeyScope]) -> list[ApiKeyScope]:
        if not v:
            raise ValueError("ao menos um scope é obrigatório")
        return v


# Retornado apenas UMA vez, na criação — inclui a chave completa em plaintext.
class ApiKeyCreatedResponse(BaseModel):
    id: uuid.UUID
    name: str
    prefix: str
    scopes: list[str]
    api_key: str


class ApiKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    prefix: str
    scopes: list[str]
    status: ApiKeyStatus
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
