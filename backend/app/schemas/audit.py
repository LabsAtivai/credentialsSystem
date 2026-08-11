import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AuditAction


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    api_key_id: uuid.UUID | None
    action: AuditAction
    resource: str
    resource_id: str | None
    ip_address: str | None
    user_agent: str | None
    metadata: dict | None = Field(default=None, alias="metadata_")
    created_at: datetime


class PaginatedAuditLogs(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
