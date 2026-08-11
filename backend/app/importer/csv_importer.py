import csv
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import AuditAction
from app.models.snov_account import SnovAccount
from app.schemas.account import SnovAccountCreate
from app.services.audit import audit_service
from app.services.encryption import encryption_service

REQUIRED_LOGICAL_FIELDS = {"email", "snov_id", "snov_secret", "snov_email", "snov_password"}

# Colunas aceitas na planilha original (email, snov_id, snov_secret, snovemail, snovsenha)
# mapeadas para os nomes lógicos usados internamente.
_HEADER_ALIASES = {
    "email": "email",
    "snovid": "snov_id",
    "snov_id": "snov_id",
    "snovsecret": "snov_secret",
    "snov_secret": "snov_secret",
    "snovemail": "snov_email",
    "snov_email": "snov_email",
    "snovsenha": "snov_password",
    "snovpassword": "snov_password",
    "snov_password": "snov_password",
    "snov_senha": "snov_password",
    "description": "description",
    "descricao": "description",
    "descrição": "description",
}

# Campos sensíveis — mensagem de erro nunca ecoa o valor de entrada.
_SENSITIVE_FIELDS = {"snov_secret", "snov_email", "snov_password"}

RowAction = Literal["new", "update", "duplicate", "invalid"]


@dataclass
class ImportRowResult:
    row_number: int
    action: RowAction
    email: str | None = None
    errors: list[str] = field(default_factory=list)


@dataclass
class ImportSummary:
    total: int = 0
    valid: int = 0
    invalid: int = 0
    duplicates: int = 0
    new: int = 0
    updates: int = 0
    rows: list[ImportRowResult] = field(default_factory=list)


class ImportError(Exception):
    pass


def _normalize_header(name: str) -> str:
    return name.strip().lower().replace(" ", "").replace("-", "")


def _build_header_map(fieldnames: list[str] | None) -> dict[str, str]:
    if not fieldnames:
        raise ImportError("Arquivo CSV sem cabeçalho.")

    header_map: dict[str, str] = {}
    for original in fieldnames:
        normalized = _normalize_header(original)
        logical = _HEADER_ALIASES.get(normalized)
        if logical:
            header_map[original] = logical

    found_logical = set(header_map.values())
    missing = REQUIRED_LOGICAL_FIELDS - found_logical
    if missing:
        raise ImportError(f"Colunas obrigatórias ausentes no CSV: {', '.join(sorted(missing))}")

    return header_map


def _format_validation_errors(exc: ValidationError) -> list[str]:
    messages = []
    for err in exc.errors():
        field_name = str(err["loc"][-1]) if err["loc"] else "?"
        if field_name in _SENSITIVE_FIELDS:
            messages.append(f"{field_name}: valor inválido (detalhe omitido por segurança)")
        else:
            messages.append(f"{field_name}: {err['msg']}")
    return messages


def _read_rows(file_path: Path) -> tuple[dict[str, str], list[dict[str, str]]]:
    with file_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        header_map = _build_header_map(reader.fieldnames)
        rows = list(reader)
    return header_map, rows


def run_import(
    file_path: str | Path,
    db: Session,
    *,
    persist: bool,
    actor_id: uuid.UUID | None = None,
    actor_ip: str | None = None,
) -> ImportSummary:
    """Analisa (e opcionalmente grava) um CSV de contas Snov.

    Sempre faz uma passada única: detecta duplicados dentro do próprio arquivo,
    decide se cada linha válida é NOVA ou ATUALIZAÇÃO de conta existente, e,
    quando persist=True, grava (criptografando) e audita cada mudança.
    Uma linha inválida não interrompe as demais.
    """
    path = Path(file_path)
    if not path.exists():
        raise ImportError(f"Arquivo não encontrado: {path}")

    header_map, raw_rows = _read_rows(path)

    summary = ImportSummary(total=len(raw_rows))
    seen_emails: set[str] = set()
    seen_snov_hashes: set[str] = set()

    for row_number, raw_row in enumerate(raw_rows, start=2):  # linha 1 é o cabeçalho
        mapped = {logical: (raw_row.get(original) or "").strip() for original, logical in header_map.items()}
        description = mapped.pop("description", None) or None

        try:
            payload = SnovAccountCreate(**mapped, description=description)
        except ValidationError as exc:
            summary.invalid += 1
            summary.rows.append(
                ImportRowResult(
                    row_number=row_number,
                    action="invalid",
                    email=mapped.get("email") or None,
                    errors=_format_validation_errors(exc),
                )
            )
            continue

        lookup_hash = encryption_service.hash_for_lookup(payload.snov_email)

        if payload.email in seen_emails or lookup_hash in seen_snov_hashes:
            summary.duplicates += 1
            summary.rows.append(
                ImportRowResult(row_number=row_number, action="duplicate", email=payload.email)
            )
            continue

        seen_emails.add(payload.email)
        seen_snov_hashes.add(lookup_hash)
        summary.valid += 1

        existing = (
            db.query(SnovAccount)
            .filter(
                (SnovAccount.email == payload.email)
                | (SnovAccount.snov_email_lookup_hash == lookup_hash)
            )
            .filter(SnovAccount.deleted_at.is_(None))
            .first()
        )
        action: RowAction = "update" if existing else "new"
        if action == "new":
            summary.new += 1
        else:
            summary.updates += 1
        summary.rows.append(ImportRowResult(row_number=row_number, action=action, email=payload.email))

        if not persist:
            continue

        try:
            with db.begin_nested():
                if existing:
                    existing.snov_id = payload.snov_id
                    existing.snov_secret_encrypted = encryption_service.encrypt(payload.snov_secret)
                    existing.snov_email_encrypted = encryption_service.encrypt(payload.snov_email)
                    existing.snov_password_encrypted = encryption_service.encrypt(payload.snov_password)
                    existing.snov_email_lookup_hash = lookup_hash
                    if payload.description is not None:
                        existing.description = payload.description
                    existing.updated_by = actor_id
                    account_id = existing.id
                    audit_action = AuditAction.ACCOUNT_UPDATED
                else:
                    account = SnovAccount(
                        email=payload.email,
                        snov_id=payload.snov_id,
                        snov_secret_encrypted=encryption_service.encrypt(payload.snov_secret),
                        snov_email_encrypted=encryption_service.encrypt(payload.snov_email),
                        snov_password_encrypted=encryption_service.encrypt(payload.snov_password),
                        snov_email_lookup_hash=lookup_hash,
                        description=payload.description,
                        created_by=actor_id,
                        updated_by=actor_id,
                    )
                    db.add(account)
                    db.flush()
                    account_id = account.id
                    audit_action = AuditAction.ACCOUNT_CREATED

                audit_service.log(
                    db,
                    action=audit_action,
                    resource="snov_account",
                    resource_id=account_id,
                    user_id=actor_id,
                    ip_address=actor_ip,
                    metadata={"email": payload.email, "source": "csv_import"},
                )
        except IntegrityError:
            # condição de corrida rara (registro criado por outra requisição entre a checagem e o insert)
            summary.valid -= 1
            if action == "new":
                summary.new -= 1
            else:
                summary.updates -= 1
            summary.duplicates += 1
            summary.rows[-1] = ImportRowResult(
                row_number=row_number, action="duplicate", email=payload.email
            )

    if persist:
        db.commit()

    return summary
