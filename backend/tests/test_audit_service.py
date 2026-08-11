import uuid
from unittest.mock import MagicMock

import pytest

from app.models.enums import AuditAction
from app.services.audit import AuditService, ForbiddenAuditMetadataError


@pytest.mark.parametrize(
    "metadata",
    [
        {"snov_password": "123456"},
        {"snov_secret": "abc"},
        {"snov_email": "conta@snov.io"},
        {"password": "hunter2"},
        {"token": "eyJ..."},
        {"jwt": "eyJ..."},
        {"api_key": "sk_live_xxx"},
        {"encryption_key": "base64key"},
        {"changedFields": {"newSnovSecret": "abc"}},  # aninhado
        {"items": [{"password": "x"}]},  # dentro de lista
        {"Snov-Secret": "abc"},  # variação de formatação de chave
    ],
)
def test_log_rejects_forbidden_metadata(metadata):
    db = MagicMock()

    with pytest.raises(ForbiddenAuditMetadataError):
        AuditService.log(
            db,
            action=AuditAction.ACCOUNT_UPDATED,
            resource="snov_account",
            metadata=metadata,
        )

    db.add.assert_not_called()


def test_log_rejects_jwt_shaped_value_under_innocuous_key():
    db = MagicMock()
    jwt_like = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.4Adcj3UFmA2Iu8b0K7lQ7v9G2u9y6t4z0x1w2v3u4t5"

    with pytest.raises(ForbiddenAuditMetadataError):
        AuditService.log(
            db,
            action=AuditAction.ACCOUNT_UPDATED,
            resource="snov_account",
            metadata={"note": jwt_like},
        )

    db.add.assert_not_called()


def test_log_accepts_safe_metadata_and_persists():
    db = MagicMock()

    entry = AuditService.log(
        db,
        action=AuditAction.ACCOUNT_UPDATED,
        resource="snov_account",
        resource_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        ip_address="127.0.0.1",
        user_agent="pytest",
        metadata={"email": "cliente@example.com", "changed_fields": ["status", "description"]},
    )

    db.add.assert_called_once_with(entry)
    db.flush.assert_called_once()
    assert entry.action == AuditAction.ACCOUNT_UPDATED
    assert entry.resource == "snov_account"
    assert entry.metadata_ == {"email": "cliente@example.com", "changed_fields": ["status", "description"]}


def test_log_allows_none_metadata():
    db = MagicMock()

    entry = AuditService.log(
        db,
        action=AuditAction.LOGIN_SUCCESS,
        resource="auth",
    )

    assert entry.metadata_ is None
    db.add.assert_called_once()
