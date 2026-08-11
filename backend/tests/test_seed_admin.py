import sys
import uuid

from app.core.security import verify_password
from app.db.session import SessionLocal
from app.models.user import User
from app.seed_admin import main


def test_seed_admin_prompts_for_password_when_flag_omitted(monkeypatch):
    email = f"seed-{uuid.uuid4().hex[:10]}@example.com"
    monkeypatch.setattr(sys, "argv", ["seed_admin", "--name", "Admin Teste", "--email", email])
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "senha-digitada-no-prompt")

    main()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        assert verify_password("senha-digitada-no-prompt", user.password_hash)
    finally:
        db.close()
