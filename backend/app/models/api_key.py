import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ApiKeyScope, ApiKeyStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ApiKey(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "api_keys"

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Nunca armazenar a chave completa em plaintext — somente o hash (SHA-256).
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    # Prefixo plaintext (ex: "sk_live_abc1") só para identificação visual, não permite reconstruir a chave.
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)

    scopes: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)

    status: Mapped[ApiKeyStatus] = mapped_column(
        Enum(ApiKeyStatus, name="api_key_status"),
        nullable=False,
        default=ApiKeyStatus.ACTIVE,
        index=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    def has_scope(self, scope: ApiKeyScope) -> bool:
        return scope.value in self.scopes
