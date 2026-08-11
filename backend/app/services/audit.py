import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.enums import AuditAction

FORBIDDEN_METADATA_KEYS = {
    "snov_password",
    "snov_secret",
    "snov_email",
    "password",
    "token",
    "jwt",
    "api_key",
    "apikey",
    "encryption_key",
    "secret",
}

# Filtro por nome de campo não pega valor livre de texto passado sob uma chave
# inofensiva (ex: {"note": "<jwt real aqui>"}). Formato de JWT é reconhecível e
# de baixíssimo falso-positivo, então barramos isso também como defesa extra.
_JWT_SHAPE_RE = re.compile(r"^eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*$")


class ForbiddenAuditMetadataError(ValueError):
    pass


def _normalize_key(key: str) -> str:
    return key.strip().lower().replace("-", "_").replace(" ", "_")


def _assert_safe_metadata(value: Any, path: str = "") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = _normalize_key(str(key))
            if any(forbidden in normalized for forbidden in FORBIDDEN_METADATA_KEYS):
                raise ForbiddenAuditMetadataError(
                    f"Campo proibido em audit metadata: '{path}{key}'. "
                    "Nunca inclua senhas, secrets, tokens ou chaves no log de auditoria."
                )
            _assert_safe_metadata(nested, path=f"{path}{key}.")
    elif isinstance(value, list):
        for item in value:
            _assert_safe_metadata(item, path=path)
    elif isinstance(value, str) and _JWT_SHAPE_RE.match(value):
        raise ForbiddenAuditMetadataError(
            f"Valor em '{path.rstrip('.')}' tem formato de JWT — não pode ir pro log de auditoria."
        )


class AuditService:
    """Serviço central de auditoria. Nenhuma outra parte do sistema deve gravar em AuditLog diretamente."""

    @staticmethod
    def log(
        db: Session,
        *,
        action: AuditAction,
        resource: str,
        resource_id: str | uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        api_key_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        _assert_safe_metadata(metadata)

        entry = AuditLog(
            action=action,
            resource=resource,
            resource_id=str(resource_id) if resource_id is not None else None,
            user_id=user_id,
            api_key_id=api_key_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata_=metadata,
        )
        db.add(entry)
        db.flush()
        return entry


audit_service = AuditService()
