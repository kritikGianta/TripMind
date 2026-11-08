"""Operational commands.

python -m app.cli seed                 Create the demo traveller and admin accounts (idempotent)
python -m app.cli create-admin         Create an admin account (password read from a prompt)
python -m app.cli openapi PATH         Write the OpenAPI schema
python -m app.cli data generate        Write the synthetic demo dataset ZIP
python -m app.cli data profile PATH    Describe a dataset and draft a mapping for it
python -m app.cli data import PATH     Import a dataset ZIP or folder with a named mapping
python -m app.cli data bootstrap       Import the synthetic dataset if none is published yet
python -m app.cli demo-scenario        Fill the demo traveller with a ready-made story
"""

from __future__ import annotations

import argparse
import getpass
import json
import secrets
import sys
import tempfile
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.clock import SystemClock
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.request_context import RequestMeta
from app.core.security import hash_password
from app.datagen.generator import GeneratorOptions, generate
from app.db.session import get_session_factory
from app.models import User
from app.modules.auth.models import UserRole
from app.modules.auth.repository import UserRepository
from app.modules.ingestion.models import ImportRun
from app.modules.ingestion.repository import ImportRunRepository
from app.modules.ingestion.service import Actor, ImportService
from app.modules.ingestion.sources import open_source

_CLI_ACTOR = Actor(user_id=None, via="cli", meta=RequestMeta(ip_address=None, user_agent="cli"))


def _ensure_user(session: Session, *, email: str, full_name: str, role: UserRole) -> bool:
    users = UserRepository(session)
    if users.get_by_email(email) is not None:
        return False
    # Demo accounts are reached through one-click demo login, so their password is random and
    # never printed. Real accounts are created through sign-up or `create-admin`.
    users.add(
        User(
            email=email.lower(),
            full_name=full_name,
            password_hash=hash_password(secrets.token_urlsafe(24)),
            role=role,
        )
    )
    return True


def seed() -> int:
    settings = get_settings()
    with get_session_factory()() as session:
        created = [
            email
            for email, name, role in (
                (settings.demo_traveler_email, "Demo Traveller", UserRole.TRAVELER),
                (settings.demo_admin_email, "Demo Admin", UserRole.ADMIN),
            )
            if _ensure_user(session, email=email, full_name=name, role=role)
        ]
        session.commit()
    print(
        f"seed: created {len(created)} demo account(s)"
        + (f": {', '.join(created)}" if created else "")
    )
    return 0


def create_admin(email: str, full_name: str) -> int:
    password = getpass.getpass("Password (min 8 characters): ")
    if len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        return 2
    with get_session_factory()() as session:
        users = UserRepository(session)
        if users.get_by_email(email) is not None:
            print(f"An account already exists for {email}.", file=sys.stderr)
            return 1
        users.add(
            User(
                email=email.lower(),
                full_name=full_name,
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
            )
        )
        session.commit()
    print(f"Created admin {email}")
    return 0


def export_openapi(path: Path) -> int:
    from app.main import create_app  # imported lazily: builds the full application

    schema = create_app().openapi()
    path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {path}")
    return 0


# ------------------------------------------------------------------------------ datasets


def data_generate(
    out: Path,
    *,
    seed: int,
    start: date | None,
    days: int,
    dirty: float,
    flight_format: str = "dated",
) -> int:
    options = GeneratorOptions(
        seed=seed,
        start=start or date.today(),
        days=days,
        dirty_rate=dirty,
        flight_format=flight_format,
    )
    result = generate(out, options)
    counts = ", ".join(f"{k} {v}" for k, v in result.counts.items())
    print(f"Wrote {result.path} ({counts}; corrupted rows: {sum(result.corrupted.values())})")
    return 0


def _print_run(run: ImportRun) -> None:
    print(f"Import {run.id}: {run.status.upper()} in {run.duration_ms} ms")
    for entity, counts in (run.entity_counts or {}).items():
        print(f"  {entity:<11}" + "  ".join(f"{k} {v}" for k, v in counts.items()))
    for code, n in ((run.adjustments or {}).get("counts") or {}).items():
        print(f"  adjusted   {code}: {n}")
    for entity, codes in (run.reject_summary or {}).items():
        print(f"  rejected   {entity}: " + ", ".join(f"{c} {n}" for c, n in codes.items()))
    window = (run.profile or {}).get("travel_window")
    if window:
        print(f"  travel window {window['first_departure']} to {window['last_departure']}")
    if run.error:
        print(f"  {run.error}")


def data_import(path: Path, mapping: str, *, dry_run: bool) -> int:
    settings = get_settings()
    with get_session_factory()() as session:
        service = ImportService(session, settings, SystemClock())
        rules = service.rules()
        try:
            source = open_source(
                path,
                max_members=rules.max_archive_members,
                max_uncompressed_mb=rules.max_uncompressed_mb,
            )
            run = service.run_import(
                source, mapping_name=mapping, dry_run=dry_run, actor=_CLI_ACTOR
            )
        except DomainError as exc:
            print(f"Import failed [{exc.code}]: {exc.message}", file=sys.stderr)
            if exc.details:
                print(json.dumps(exc.details, indent=2, default=str), file=sys.stderr)
            return 1
    _print_run(run)
    return 0 if run.status in {"published", "validated"} else 1


def data_profile(path: Path, dataset: str, write: Path | None) -> int:
    settings = get_settings()
    with get_session_factory()() as session:
        service = ImportService(session, settings, SystemClock())
        rules = service.rules()
        source = open_source(
            path,
            max_members=rules.max_archive_members,
            max_uncompressed_mb=rules.max_uncompressed_mb,
        )
        profiles, suggestion = service.profile(source, dataset)
    for profile in profiles:
        print(f"{profile['file']}: {profile['rows']} rows, encoding {profile['encoding']}")
        for col in profile["columns"]:
            fmt = f" [{col['format']}]" if col["format"] else ""
            print(
                f"  {col['name']:<24} {col['kind'] + fmt:<30} nulls {col['null_pct']:>5}%  "
                f"e.g. {', '.join(col['samples'])}"
            )
    if write:
        write.write_text(suggestion, encoding="utf-8")
        print(f"Draft mapping written to {write}. Review it before importing.")
    else:
        print()
        print(suggestion)
    return 0


def data_bootstrap() -> int:
    """Used by Docker Compose: load the demo dataset once, through the normal pipeline."""
    with get_session_factory()() as session:
        if ImportRunRepository(session).latest_published() is not None:
            print("bootstrap: a dataset is already published; nothing to do")
            return 0
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "synthetic-v1.zip"
        data_generate(archive, seed=7, start=None, days=45, dirty=0.004)
        return data_import(archive, "synthetic-v1", dry_run=False)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed", help="Create demo accounts")
    demo = sub.add_parser("demo-scenario", help="Fill the demo traveller with a ready-made story")
    demo.add_argument(
        "--fresh", action="store_true", help="Archive the current demo traveller and start again"
    )
    admin = sub.add_parser("create-admin", help="Create an admin account")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", default="Administrator")
    openapi = sub.add_parser("openapi", help="Write the OpenAPI schema to a file")
    openapi.add_argument("path", type=Path)

    data = sub.add_parser("data", help="Dataset generation, profiling and import")
    data_sub = data.add_subparsers(dest="data_command", required=True)
    gen = data_sub.add_parser("generate", help="Write the synthetic demo dataset ZIP")
    gen.add_argument("--out", type=Path, default=Path("../data/generated/synthetic-v1.zip"))
    gen.add_argument("--seed", type=int, default=7)
    gen.add_argument(
        "--start",
        type=date.fromisoformat,
        default=None,
        help="First travel date, YYYY-MM-DD (default: today)",
    )
    gen.add_argument("--days", type=int, default=45)
    gen.add_argument(
        "--dirty",
        type=float,
        default=0.004,
        help="Share of rows corrupted on purpose (0 for a clean file)",
    )
    gen.add_argument(
        "--flight-format",
        choices=["dated", "schedules"],
        default="dated",
        help="Dated flights, or repeating airline schedules",
    )
    prof = data_sub.add_parser("profile", help="Profile a dataset and draft a mapping")
    prof.add_argument("path", type=Path)
    prof.add_argument("--dataset", default="finale")
    prof.add_argument("--write", type=Path, default=None, help="Save the draft mapping here")
    imp = data_sub.add_parser("import", help="Import a dataset ZIP or folder")
    imp.add_argument("path", type=Path)
    imp.add_argument("--mapping", required=True, help="Name of a file in config/mappings")
    imp.add_argument("--dry-run", action="store_true", help="Validate without publishing")
    data_sub.add_parser("bootstrap", help="Import the synthetic dataset if none is published")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "seed":
        return seed()
    if args.command == "demo-scenario":
        from app.demo import run  # imported lazily: pulls in every service

        print(run(get_settings(), fresh=args.fresh))
        return 0
    if args.command == "openapi":
        return export_openapi(args.path)
    if args.command == "create-admin":
        return create_admin(args.email, args.name)
    if args.data_command == "generate":
        return data_generate(
            args.out,
            seed=args.seed,
            start=args.start,
            days=args.days,
            dirty=args.dirty,
            flight_format=args.flight_format,
        )
    if args.data_command == "profile":
        return data_profile(args.path, args.dataset, args.write)
    if args.data_command == "import":
        return data_import(args.path, args.mapping, dry_run=args.dry_run)
    return data_bootstrap()


if __name__ == "__main__":
    raise SystemExit(main())
