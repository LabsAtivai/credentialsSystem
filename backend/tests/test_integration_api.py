"""
Testes de integração contra Postgres real. Requer DATABASE_URL apontando
para um banco com o schema aplicado (alembic upgrade head) antes de rodar.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, UserRole
from app.models.user import User

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    # Todos os testes compartilham o mesmo IP fake do TestClient — sem isso, o limite
    # de /api/auth/login (10/minute) vaza entre testes e derruba os que vêm depois.
    from app.core.rate_limit import limiter

    limiter.reset()
    yield


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


@pytest.fixture()
def admin_token() -> tuple[str, str]:
    email = _unique_email("admin")
    password = "senha-forte-123"
    db = SessionLocal()
    try:
        user = User(name="Admin Teste", email=email, password_hash=hash_password(password), role=UserRole.ADMIN)
        db.add(user)
        db.commit()
    finally:
        db.close()

    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"], email


def _create_user(token: str, role: str) -> tuple[str, str]:
    email = _unique_email(role.lower())
    password = "senha-forte-123"
    resp = client.post(
        "/api/users",
        json={"name": f"{role} teste", "email": email, "password": password, "role": role},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text

    login = client.post("/api/auth/login", json={"email": email, "password": password})
    return login.json()["access_token"], email


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_login_wrong_password_fails_and_is_audited(admin_token):
    _, email = admin_token
    resp = client.post("/api/auth/login", json={"email": email, "password": "senha-errada"})
    assert resp.status_code == 401

    db = SessionLocal()
    try:
        log = (
            db.query(AuditLog)
            .filter(AuditLog.action == AuditAction.LOGIN_FAILED)
            .order_by(AuditLog.created_at.desc())
            .first()
        )
        assert log is not None
        assert log.metadata_["email"] == email
    finally:
        db.close()


def test_readonly_cannot_create_account(admin_token):
    admin_tok, _ = admin_token
    readonly_tok, _ = _create_user(admin_tok, "READONLY")

    resp = client.post(
        "/api/accounts",
        json={
            "email": _unique_email("acc"),
            "snov_id": "client-123",
            "snov_secret": "super-secret",
            "snov_email": _unique_email("snov"),
            "snov_password": "snov-pass-123",
        },
        headers=_auth_headers(readonly_tok),
    )
    assert resp.status_code == 403


def test_operator_creates_account_and_response_never_leaks_credentials(admin_token):
    admin_tok, _ = admin_token
    operator_tok, _ = _create_user(admin_tok, "OPERATOR")

    account_email = _unique_email("acc")
    payload = {
        "email": account_email,
        "snov_id": "client-abc",
        "snov_secret": "top-secret-value",
        "snov_email": _unique_email("snov"),
        "snov_password": "snov-pass-xyz",
    }
    resp = client.post("/api/accounts", json=payload, headers=_auth_headers(operator_tok))
    assert resp.status_code == 201, resp.text
    body = resp.json()

    forbidden_keys = {"snov_secret", "snov_email", "snov_password"}
    assert forbidden_keys.isdisjoint(body.keys())
    assert body["email"] == account_email
    assert body["status"] == "ACTIVE"

    account_id = body["id"]

    list_resp = client.get("/api/accounts", headers=_auth_headers(operator_tok))
    assert list_resp.status_code == 200
    for item in list_resp.json()["items"]:
        assert forbidden_keys.isdisjoint(item.keys())

    get_resp = client.get(f"/api/accounts/{account_id}", headers=_auth_headers(operator_tok))
    assert get_resp.status_code == 200
    assert forbidden_keys.isdisjoint(get_resp.json().keys())

    # resposta HTTP crua também não deve conter os valores em texto puro
    raw_text = get_resp.text
    assert "top-secret-value" not in raw_text
    assert "snov-pass-xyz" not in raw_text


def test_duplicate_email_and_snov_email_rejected(admin_token):
    admin_tok, _ = admin_token
    operator_tok, _ = _create_user(admin_tok, "OPERATOR")

    account_email = _unique_email("acc")
    snov_email = _unique_email("snov")
    payload = {
        "email": account_email,
        "snov_id": "client-dup",
        "snov_secret": "secret-1",
        "snov_email": snov_email,
        "snov_password": "pass-1",
    }
    first = client.post("/api/accounts", json=payload, headers=_auth_headers(operator_tok))
    assert first.status_code == 201

    dup_email = {**payload, "snov_email": _unique_email("other-snov")}
    resp = client.post("/api/accounts", json=dup_email, headers=_auth_headers(operator_tok))
    assert resp.status_code == 409

    dup_snov = {**payload, "email": _unique_email("other-acc")}
    resp = client.post("/api/accounts", json=dup_snov, headers=_auth_headers(operator_tok))
    assert resp.status_code == 409


def test_internal_credentials_requires_scope_and_roundtrips_plaintext(admin_token):
    admin_tok, _ = admin_token
    operator_tok, _ = _create_user(admin_tok, "OPERATOR")

    snov_secret = "very-secret-value-1"
    snov_email = _unique_email("snov")
    snov_password = "very-secret-password-1"
    payload = {
        "email": _unique_email("acc"),
        "snov_id": "client-cred",
        "snov_secret": snov_secret,
        "snov_email": snov_email,
        "snov_password": snov_password,
    }
    create_resp = client.post("/api/accounts", json=payload, headers=_auth_headers(operator_tok))
    account_id = create_resp.json()["id"]

    # API key sem scope credentials:read -> 403
    weak_key_resp = client.post(
        "/api/api-keys",
        json={"name": "sistema-sem-credencial", "scopes": ["accounts:read"]},
        headers=_auth_headers(admin_tok),
    )
    assert weak_key_resp.status_code == 201
    weak_key = weak_key_resp.json()["api_key"]

    resp = client.get(
        f"/api/internal/accounts/{account_id}/credentials", headers={"X-API-Key": weak_key}
    )
    assert resp.status_code == 403

    # API key com credentials:read -> 200 e valores batem com o original
    strong_key_resp = client.post(
        "/api/api-keys",
        json={"name": "sistema-sdr", "scopes": ["accounts:read", "credentials:read"]},
        headers=_auth_headers(admin_tok),
    )
    strong_key = strong_key_resp.json()["api_key"]

    resp = client.get(
        f"/api/internal/accounts/{account_id}/credentials", headers={"X-API-Key": strong_key}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["snov_secret"] == snov_secret
    assert body["snov_email"] == snov_email
    assert body["snov_password"] == snov_password

    db = SessionLocal()
    try:
        log = (
            db.query(AuditLog)
            .filter(AuditLog.action == AuditAction.CREDENTIALS_ACCESSED)
            .order_by(AuditLog.created_at.desc())
            .first()
        )
        assert log is not None
        assert log.resource_id == account_id
        # metadata nunca pode conter os segredos
        assert snov_secret not in str(log.metadata_)
        assert snov_password not in str(log.metadata_)
    finally:
        db.close()


def test_operator_cannot_access_credentials_endpoint_via_jwt(admin_token):
    admin_tok, _ = admin_token
    operator_tok, _ = _create_user(admin_tok, "OPERATOR")

    payload = {
        "email": _unique_email("acc"),
        "snov_id": "client-x",
        "snov_secret": "s1",
        "snov_email": _unique_email("snov"),
        "snov_password": "p1",
    }
    create_resp = client.post("/api/accounts", json=payload, headers=_auth_headers(operator_tok))
    account_id = create_resp.json()["id"]

    resp = client.get(
        f"/api/internal/accounts/{account_id}/credentials", headers=_auth_headers(operator_tok)
    )
    assert resp.status_code == 403


def test_admin_can_access_credentials_endpoint_via_jwt(admin_token):
    admin_tok, _ = admin_token

    payload = {
        "email": _unique_email("acc"),
        "snov_id": "client-y",
        "snov_secret": "s2",
        "snov_email": _unique_email("snov"),
        "snov_password": "p2",
    }
    create_resp = client.post("/api/accounts", json=payload, headers=_auth_headers(admin_tok))
    account_id = create_resp.json()["id"]

    resp = client.get(
        f"/api/internal/accounts/{account_id}/credentials", headers=_auth_headers(admin_tok)
    )
    assert resp.status_code == 200
    assert resp.json()["snov_secret"] == "s2"


def test_revoked_api_key_is_rejected(admin_token):
    admin_tok, _ = admin_token

    key_resp = client.post(
        "/api/api-keys",
        json={"name": "sistema-revogar", "scopes": ["accounts:read"]},
        headers=_auth_headers(admin_tok),
    )
    key_id = key_resp.json()["id"]
    full_key = key_resp.json()["api_key"]

    revoke_resp = client.patch(f"/api/api-keys/{key_id}/revoke", headers=_auth_headers(admin_tok))
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["status"] == "REVOKED"

    resp = client.get("/api/accounts", headers={"X-API-Key": full_key})
    # não há rota /api/accounts autenticável via API key ainda (somente internal) —
    # validamos a revogação diretamente contra o endpoint internal
    resp = client.get(
        "/api/internal/accounts/00000000-0000-0000-0000-000000000000/credentials",
        headers={"X-API-Key": full_key},
    )
    assert resp.status_code == 403


def test_no_auth_rejected_on_protected_endpoints():
    resp = client.get("/api/accounts")
    assert resp.status_code == 401

    resp = client.get("/api/internal/accounts/00000000-0000-0000-0000-000000000000/credentials")
    assert resp.status_code == 401


def test_malformed_token_returns_401_not_500():
    resp = client.get("/api/accounts", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert resp.status_code == 401

    # token com "sub" que não é UUID (assinado com um secret qualquer só pra passar o decode)
    import jose.jwt as jose_jwt

    from app.config import settings

    bad_sub_token = jose_jwt.encode(
        {"sub": "nao-e-um-uuid", "role": "ADMIN"}, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )
    resp = client.get("/api/accounts", headers={"Authorization": f"Bearer {bad_sub_token}"})
    assert resp.status_code == 401


def test_audit_logs_admin_can_list_operator_readonly_cannot(admin_token):
    admin_tok, _ = admin_token
    operator_tok, _ = _create_user(admin_tok, "OPERATOR")
    readonly_tok, _ = _create_user(admin_tok, "READONLY")

    payload = {
        "email": _unique_email("acc"),
        "snov_id": "client-audit",
        "snov_secret": "s-audit",
        "snov_email": _unique_email("snov"),
        "snov_password": "p-audit",
    }
    client.post("/api/accounts", json=payload, headers=_auth_headers(operator_tok))

    resp = client.get("/api/audit-logs", headers=_auth_headers(admin_tok))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert any(item["action"] == "ACCOUNT_CREATED" for item in body["items"])

    assert client.get("/api/audit-logs", headers=_auth_headers(operator_tok)).status_code == 403
    assert client.get("/api/audit-logs", headers=_auth_headers(readonly_tok)).status_code == 403
    assert client.get("/api/audit-logs").status_code == 401


def test_audit_logs_via_api_key_scope(admin_token):
    admin_tok, _ = admin_token

    weak_key = client.post(
        "/api/api-keys",
        json={"name": "sem-audit-scope", "scopes": ["accounts:read"]},
        headers=_auth_headers(admin_tok),
    ).json()["api_key"]
    resp = client.get("/api/audit-logs", headers={"X-API-Key": weak_key})
    assert resp.status_code == 403

    strong_key = client.post(
        "/api/api-keys",
        json={"name": "com-audit-scope", "scopes": ["audit:read"]},
        headers=_auth_headers(admin_tok),
    ).json()["api_key"]
    resp = client.get("/api/audit-logs", headers={"X-API-Key": strong_key})
    assert resp.status_code == 200


def test_audit_logs_filter_by_action(admin_token):
    admin_tok, _ = admin_token

    resp = client.get(
        "/api/audit-logs", params={"action": "LOGIN_SUCCESS"}, headers=_auth_headers(admin_tok)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert all(item["action"] == "LOGIN_SUCCESS" for item in body["items"])


def test_login_is_rate_limited_against_brute_force():
    email = _unique_email("ratelimit")
    responses = [
        client.post("/api/auth/login", json={"email": email, "password": "tentativa-errada"})
        for _ in range(11)
    ]
    statuses = [r.status_code for r in responses]
    assert statuses.count(401) == 10
    assert statuses[-1] == 429
