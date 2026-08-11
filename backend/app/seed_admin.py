import argparse
import getpass
import sys

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.enums import UserRole
from app.models.user import User


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cria o primeiro usuário ADMIN do Snov Account Manager."
    )
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument(
        "--password",
        help="Se omitido, pede via prompt oculto (recomendado — evita senha em "
        "histórico de shell / lista de processos). Use a flag só em automação não-interativa.",
    )
    args = parser.parse_args()

    password = args.password or getpass.getpass("Senha do ADMIN: ")

    if len(password) < 8:
        print("Senha deve ter ao menos 8 caracteres.", file=sys.stderr)
        raise SystemExit(1)

    email = args.email.strip().lower()

    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email).first():
            print(f"Usuário {email} já existe. Nada a fazer.")
            return

        user = User(
            name=args.name.strip(),
            email=email,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
        )
        db.add(user)
        db.commit()
        print(f"Usuário ADMIN criado: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
