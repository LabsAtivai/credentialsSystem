"""
Testes de integração do importador CSV. Requer DATABASE_URL apontando
para um banco com o schema aplicado (alembic upgrade head).
"""

import uuid
from pathlib import Path

import pytest

from app.db.session import SessionLocal
from app.importer.csv_importer import ImportError as ImportFileError
from app.importer.csv_importer import run_import
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction
from app.models.snov_account import SnovAccount
from app.services.encryption import encryption_service


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


def _write_csv(tmp_path: Path, header: str, rows: list[str]) -> Path:
    content = "\n".join([header, *rows]) + "\n"
    path = tmp_path / "import.csv"
    path.write_text(content, encoding="utf-8")
    return path


def test_dry_run_never_writes_to_db(tmp_path, db):
    email = _unique_email("dry")
    snov_email = _unique_email("snovdry")
    csv_path = _write_csv(
        tmp_path,
        "email,snov_id,snov_secret,snovemail,snovsenha",
        [f"{email},client-1,secret-1,{snov_email},pass-1"],
    )

    summary = run_import(csv_path, db, persist=False)

    assert summary.total == 1
    assert summary.valid == 1
    assert summary.new == 1
    assert summary.invalid == 0
    assert summary.duplicates == 0

    exists = db.query(SnovAccount).filter(SnovAccount.email == email).first()
    assert exists is None


def test_persist_creates_account_encrypted_and_audited(tmp_path, db):
    email = _unique_email("new")
    snov_email = _unique_email("snovnew")
    csv_path = _write_csv(
        tmp_path,
        "email,snov_id,snov_secret,snovemail,snovsenha",
        [f"{email},client-2,my-secret-value,{snov_email},my-password-value"],
    )

    summary = run_import(csv_path, db, persist=True)

    assert summary.new == 1
    assert summary.invalid == 0

    account = db.query(SnovAccount).filter(SnovAccount.email == email).first()
    assert account is not None
    assert account.snov_secret_encrypted != "my-secret-value"
    assert encryption_service.decrypt(account.snov_secret_encrypted) == "my-secret-value"
    assert encryption_service.decrypt(account.snov_password_encrypted) == "my-password-value"

    log = (
        db.query(AuditLog)
        .filter(AuditLog.action == AuditAction.ACCOUNT_CREATED, AuditLog.resource_id == str(account.id))
        .first()
    )
    assert log is not None
    assert log.metadata_["source"] == "csv_import"
    assert "my-secret-value" not in str(log.metadata_)


def test_rerun_updates_existing_account_instead_of_duplicating(tmp_path, db):
    email = _unique_email("upd")
    snov_email = _unique_email("snovupd")

    csv_v1 = _write_csv(
        tmp_path,
        "email,snov_id,snov_secret,snovemail,snovsenha",
        [f"{email},client-3,secret-v1,{snov_email},pass-v1"],
    )
    first = run_import(csv_v1, db, persist=True)
    assert first.new == 1

    csv_v2 = _write_csv(
        tmp_path,
        "email,snov_id,snov_secret,snovemail,snovsenha",
        [f"{email},client-3,secret-v2,{snov_email},pass-v2"],
    )
    second = run_import(csv_v2, db, persist=True)
    assert second.updates == 1
    assert second.new == 0

    accounts = db.query(SnovAccount).filter(SnovAccount.email == email).all()
    assert len(accounts) == 1
    assert encryption_service.decrypt(accounts[0].snov_secret_encrypted) == "secret-v2"


def test_invalid_row_does_not_block_other_rows(tmp_path, db):
    good_email = _unique_email("good")
    good_snov = _unique_email("goodsnov")
    csv_path = _write_csv(
        tmp_path,
        "email,snov_id,snov_secret,snovemail,snovsenha",
        [
            "email-invalido,client-x,secret-x,snov-invalido,pass-x",
            f"{good_email},client-y,secret-y,{good_snov},pass-y",
        ],
    )

    summary = run_import(csv_path, db, persist=False)

    assert summary.total == 2
    assert summary.invalid == 1
    assert summary.valid == 1
    assert summary.new == 1

    invalid_row = next(r for r in summary.rows if r.action == "invalid")
    assert invalid_row.row_number == 2


def test_duplicate_within_same_file_only_imports_first(tmp_path, db):
    email = _unique_email("dup")
    snov_email = _unique_email("snovdup")
    csv_path = _write_csv(
        tmp_path,
        "email,snov_id,snov_secret,snovemail,snovsenha",
        [
            f"{email},client-a,secret-a,{snov_email},pass-a",
            f"{email},client-b,secret-b,{snov_email},pass-b",
        ],
    )

    summary = run_import(csv_path, db, persist=True)

    assert summary.new == 1
    assert summary.duplicates == 1

    accounts = db.query(SnovAccount).filter(SnovAccount.email == email).all()
    assert len(accounts) == 1
    assert encryption_service.decrypt(accounts[0].snov_secret_encrypted) == "secret-a"


def test_header_aliases_case_insensitive(tmp_path, db):
    email = _unique_email("alias")
    snov_email = _unique_email("snovalias")
    csv_path = _write_csv(
        tmp_path,
        "Email,SNOV_ID,SnovSecret,SnovEmail,snovsenha,Descricao",
        [f"{email},client-alias,secret-alias,{snov_email},pass-alias,Conta via alias"],
    )

    summary = run_import(csv_path, db, persist=False)

    assert summary.total == 1
    assert summary.valid == 1
    assert summary.invalid == 0


def test_missing_required_column_raises(tmp_path, db):
    csv_path = _write_csv(
        tmp_path,
        "email,snov_id,snovemail,snovsenha",  # falta snov_secret
        ["a@example.com,client,snov@example.com,pass"],
    )

    with pytest.raises(ImportFileError):
        run_import(csv_path, db, persist=False)


def test_error_messages_never_leak_sensitive_values(tmp_path, db):
    email = _unique_email("leak")
    csv_path = _write_csv(
        tmp_path,
        "email,snov_id,snov_secret,snovemail,snovsenha",
        [f"{email},client-leak,,not-an-email,pass-leak"],  # snov_secret vazio, snov_email inválido
    )

    summary = run_import(csv_path, db, persist=False)

    assert summary.invalid == 1
    row = summary.rows[0]
    joined_errors = " ".join(row.errors)
    assert "not-an-email" not in joined_errors
    assert "pass-leak" not in joined_errors
