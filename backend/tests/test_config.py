import base64
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _run_load_settings(env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", "from app.config import load_settings; load_settings()"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _base_env(**overrides: str) -> dict[str, str]:
    import os

    env = {k: v for k, v in os.environ.items() if not k.startswith(("DATABASE_URL", "JWT_SECRET", "ENCRYPTION_KEY"))}
    env["DATABASE_URL"] = "postgresql+psycopg://test:test@localhost:5432/test"
    env["JWT_SECRET"] = "test-secret"
    env["ENCRYPTION_KEY"] = base64.b64encode(b"0" * 32).decode()
    env.update(overrides)
    return env


def test_startup_fails_fast_when_encryption_key_missing():
    env = _base_env()
    del env["ENCRYPTION_KEY"]

    result = _run_load_settings(env)

    assert result.returncode != 0
    assert "ENCRYPTION_KEY" in (result.stdout + result.stderr) or "encryption_key" in (result.stdout + result.stderr).lower()


def test_startup_fails_fast_when_encryption_key_wrong_length():
    env = _base_env(ENCRYPTION_KEY=base64.b64encode(b"short").decode())

    result = _run_load_settings(env)

    assert result.returncode != 0
    assert "32" in (result.stdout + result.stderr)


def test_startup_fails_fast_when_encryption_key_not_base64():
    env = _base_env(ENCRYPTION_KEY="isto-nao-e-base64-!!!@@@")

    result = _run_load_settings(env)

    assert result.returncode != 0


def test_startup_succeeds_with_valid_key():
    env = _base_env()

    result = _run_load_settings(env)

    assert result.returncode == 0
