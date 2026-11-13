"""Command-line tasks.

python -m app.cli seed                 Create the demo traveller and admin accounts (idempotent)
python -m app.cli create-admin --email E   Create an admin account (asks for a password)
python -m app.cli openapi PATH         Write the OpenAPI schema (for the website types)
python -m app.cli holiday load         Load the official data pack + our extension
python -m app.cli holiday extend       Regenerate our extension (same schema)
"""

from __future__ import annotations

import argparse
import getpass
import json
import secrets
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import get_session_factory
from app.models import User
from app.modules.auth.models import UserRole
from app.modules.auth.repository import UserRepository


def _ensure_user(session: Session, *, email: str, full_name: str, role: UserRole) -> bool:
    users = UserRepository(session)
    if users.get_by_email(email) is not None:
        return False
    # Demo accounts are reached through one-click demo login, so their password is random and
    # never printed. Real admin accounts are created with `create-admin`.
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


def holiday_load(pack_dir: Path | None) -> int:
    """Load (or reload) the official data pack and our extension. Safe on every start-up."""
    from app.modules.holiday.pack import load_pack

    settings = get_settings()
    with get_session_factory()() as session:
        report = load_pack(
            session,
            pack_dir or settings.holiday_data_dir,
            datetime.now(UTC),
            settings.holiday_extra_dir,
        )
    counts = ", ".join(f"{n} {name}" for name, n in report.counts.items())
    print(f"holiday pack loaded: {counts}")
    return 0


def holiday_extend(start: date, end: date) -> int:
    from app.modules.holiday.extend import generate

    settings = get_settings()
    print(generate(settings.holiday_data_dir, settings.holiday_extra_dir, start, end))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed", help="Create demo accounts")
    admin = sub.add_parser("create-admin", help="Create an admin account")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", default="Administrator")
    openapi = sub.add_parser("openapi", help="Write the OpenAPI schema to a file")
    openapi.add_argument("path", type=Path)
    holiday = sub.add_parser("holiday", help="The official finale data pack")
    holiday_sub = holiday.add_subparsers(dest="holiday_command", required=True)
    hload = holiday_sub.add_parser("load", help="Load or reload the data pack into the catalog")
    hload.add_argument("--pack", type=Path, default=None, help="Data pack folder")
    hext = holiday_sub.add_parser("extend", help="Write more dates in the pack's schema")
    hext.add_argument("--start", type=date.fromisoformat, default=date(2026, 11, 13))
    hext.add_argument("--end", type=date.fromisoformat, default=date(2027, 5, 31))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "seed":
        return seed()
    if args.command == "openapi":
        return export_openapi(args.path)
    if args.command == "create-admin":
        return create_admin(args.email, args.name)
    if args.holiday_command == "extend":
        return holiday_extend(args.start, args.end)
    return holiday_load(args.pack)


if __name__ == "__main__":
    raise SystemExit(main())
