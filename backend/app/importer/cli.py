import argparse
import sys

from app.db.session import SessionLocal
from app.importer.csv_importer import ImportError as ImportFileError
from app.importer.csv_importer import ImportSummary, run_import
from app.models.user import User


def _print_summary(summary: ImportSummary, *, persisted: bool) -> None:
    print(f"Total de registros: {summary.total}")
    print(f"Válidos: {summary.valid}")
    print(f"Inválidos: {summary.invalid}")
    print(f"Duplicados (no arquivo): {summary.duplicates}")
    if persisted:
        print(f"Importados (novos): {summary.new}")
        print(f"Atualizados: {summary.updates}")
    else:
        print(f"Novos: {summary.new}")
        print(f"Atualizações: {summary.updates}")

    if summary.invalid:
        print("\nRegistros inválidos:")
        for row in summary.rows:
            if row.action == "invalid":
                print(f"  linha {row.row_number} ({row.email or 'sem email'}): {'; '.join(row.errors)}")

    if summary.duplicates:
        print("\nDuplicados ignorados (já vistos antes no mesmo arquivo):")
        for row in summary.rows:
            if row.action == "duplicate":
                print(f"  linha {row.row_number}: {row.email}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa contas Snov a partir de um CSV.")
    parser.add_argument("csv_path", help="Caminho do arquivo CSV")
    parser.add_argument("--dry-run", action="store_true", help="Apenas analisa, não grava no banco")
    parser.add_argument(
        "--yes", action="store_true", help="Não pede confirmação interativa antes de gravar"
    )
    parser.add_argument(
        "--actor-email", help="Email do usuário responsável pela importação (usado na auditoria)"
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        actor_id = None
        if args.actor_email:
            actor = db.query(User).filter(User.email == args.actor_email.strip().lower()).first()
            if actor is None:
                print(
                    f"Aviso: usuário '{args.actor_email}' não encontrado — "
                    "auditoria ficará sem usuário associado.",
                    file=sys.stderr,
                )
            else:
                actor_id = actor.id

        try:
            summary = run_import(args.csv_path, db, persist=False, actor_id=actor_id)
        except ImportFileError as exc:
            print(f"Erro: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

        _print_summary(summary, persisted=False)

        if args.dry_run:
            return

        if summary.valid == 0:
            print("\nNenhum registro válido para importar.")
            return

        if not args.yes:
            answer = input("\nDigite CONFIRM para gravar no banco: ").strip()
            if answer != "CONFIRM":
                print("Importação cancelada.")
                return

        final_summary = run_import(args.csv_path, db, persist=True, actor_id=actor_id)
        print("\n--- Importação concluída ---")
        _print_summary(final_summary, persisted=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()
