import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AccountStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class SnovAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "snov_accounts"
    __table_args__ = (
        Index("ix_snov_accounts_created_at", "created_at"),
        # consulta de registros ativos (status = ACTIVE AND deleted_at IS NULL) é o caso comum
        Index("ix_snov_accounts_active_lookup", "status", "deleted_at"),
    )

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    snov_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Campos sensíveis — SOMENTE ciphertext (AES-256-GCM). Ver app/services/encryption.py.
    snov_secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    snov_email_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    snov_password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)

    # HMAC determinístico de snov_email, usado apenas para checar duplicidade
    # sem expor ou comparar o ciphertext diretamente.
    snov_email_lookup_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )

    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, name="account_status"),
        nullable=False,
        default=AccountStatus.ACTIVE,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # Preparação para futura distribuição/rotação de contas (lógica não implementada agora).
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assigned_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
