import base64
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    environment: str = "development"

    database_url: str

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60

    encryption_key: str

    cors_origins: str = "http://localhost:5173"
    api_rate_limit: str = "100/minute"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def encryption_key_bytes(self) -> bytes:
        try:
            key = base64.b64decode(self.encryption_key, validate=True)
        except Exception as exc:
            raise RuntimeError(
                "ENCRYPTION_KEY inválida: deve ser base64 de 32 bytes (AES-256)."
            ) from exc
        if len(key) != 32:
            raise RuntimeError(
                f"ENCRYPTION_KEY tem {len(key)} bytes, esperado 32 (AES-256). "
                "Gere uma nova chave: python -c \"import os,base64;print(base64.b64encode(os.urandom(32)).decode())\""
            )
        return key


def load_settings() -> Settings:
    try:
        settings = Settings()
        # força validação da chave de criptografia no startup (fail-fast)
        settings.encryption_key_bytes
    except Exception as exc:
        print(f"FATAL: falha ao carregar configuração — {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    return settings


settings = load_settings()
