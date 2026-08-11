import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from pwdlib import PasswordHash

from app.config import settings

_password_hasher = PasswordHash.recommended()  # Argon2id

API_KEY_PREFIX = "sk_live_"


class InvalidTokenError(Exception):
    pass


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hasher.verify(password, password_hash)


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expires_minutes)
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise InvalidTokenError("Token inválido ou expirado.") from exc


def hash_api_key(full_key: str) -> str:
    return hashlib.sha256(full_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Retorna (chave_completa, prefixo, hash). A chave completa nunca é persistida."""
    full_key = f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"
    prefix = full_key[: len(API_KEY_PREFIX) + 4]
    return full_key, prefix, hash_api_key(full_key)
