"""Authentication use cases.

Each public method is one use case and owns its transaction: it either commits all of its changes
(including the audit record) or none of them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import Conflict, Forbidden, NotFound, Unauthorized
from app.core.metrics import AUTH_EVENTS
from app.core.request_context import RequestMeta
from app.core.security import (
    burn_password_check,
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.modules.audit.service import AuditService
from app.modules.auth.models import RefreshToken, User, UserRole
from app.modules.auth.repository import RefreshTokenRepository, UserRepository


@dataclass(frozen=True)
class IssuedSession:
    user: User
    access_token: str
    access_expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime


def _as_aware(value: datetime, reference: datetime) -> datetime:
    """SQLite returns naive datetimes; treat stored values as UTC."""
    return value if value.tzinfo else value.replace(tzinfo=reference.tzinfo)


class AuthService:
    def __init__(self, session: Session, settings: Settings, clock: Clock) -> None:
        self._session = session
        self._settings = settings
        self._clock = clock
        self._users = UserRepository(session)
        self._tokens = RefreshTokenRepository(session)
        self._audit = AuditService(session)

    # ── Use cases ──────────────────────────────────────────────────────────

    def register(
        self, *, email: str, password: str, full_name: str, meta: RequestMeta
    ) -> IssuedSession:
        email = email.lower()
        if self._users.get_by_email(email) is not None:
            self._fail("register", meta, reason="email_taken")
            raise Conflict("An account with this email already exists.", code="EMAIL_TAKEN")

        user = User(
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            role=UserRole.TRAVELER,
        )
        try:
            self._users.add(user)
        except IntegrityError as exc:  # concurrent sign-up with the same email
            self._session.rollback()
            raise Conflict(
                "An account with this email already exists.", code="EMAIL_TAKEN"
            ) from exc

        issued = self._start_session(user, meta)
        self._audit.record(
            action="auth.register", outcome="success", meta=meta, actor_user_id=user.id
        )
        self._session.commit()
        AUTH_EVENTS.labels(event="register", outcome="success").inc()
        return issued

    def login(self, *, email: str, password: str, meta: RequestMeta) -> IssuedSession:
        user = self._users.get_by_email(email)
        if user is None:
            burn_password_check(password)
            self._fail("login", meta, reason="unknown_email")
            raise Unauthorized("Email or password is incorrect.", code="INVALID_CREDENTIALS")

        valid, upgraded_hash = verify_password(password, user.password_hash)
        if not valid:
            self._fail("login", meta, reason="wrong_password", actor=user.id)
            raise Unauthorized("Email or password is incorrect.", code="INVALID_CREDENTIALS")
        if not user.is_active:
            self._fail("login", meta, reason="account_disabled", actor=user.id)
            raise Forbidden("This account has been disabled.", code="ACCOUNT_DISABLED")

        if upgraded_hash:
            user.password_hash = upgraded_hash
        issued = self._start_session(user, meta)
        self._audit.record(action="auth.login", outcome="success", meta=meta, actor_user_id=user.id)
        self._session.commit()
        AUTH_EVENTS.labels(event="login", outcome="success").inc()
        return issued

    def demo_login(self, *, role: UserRole, meta: RequestMeta) -> IssuedSession:
        email = (
            self._settings.demo_admin_email
            if role == UserRole.ADMIN
            else self._settings.demo_traveler_email
        )
        user = self._users.get_by_email(email)
        if user is None or not user.is_active:
            raise NotFound(
                "Demo accounts are not set up. Run the seed command.", code="DEMO_ACCOUNT_MISSING"
            )
        issued = self._start_session(user, meta)
        self._audit.record(
            action="auth.demo_login", outcome="success", meta=meta, actor_user_id=user.id
        )
        self._session.commit()
        AUTH_EVENTS.labels(event="demo_login", outcome="success").inc()
        return issued

    def refresh(self, *, refresh_token: str | None, meta: RequestMeta) -> IssuedSession:
        if not refresh_token:
            raise Unauthorized(
                "Your session has ended. Please sign in again.", code="SESSION_EXPIRED"
            )

        now = self._clock.now()
        record = self._tokens.get_by_hash_for_update(hash_refresh_token(refresh_token))
        if record is None:
            self._fail("refresh", meta, reason="unknown_token")
            raise Unauthorized(
                "Your session has ended. Please sign in again.", code="SESSION_EXPIRED"
            )

        if record.revoked_at is not None:
            # A rotated token was presented again: assume it was stolen and end every session
            # descended from the same sign-in.
            self._tokens.revoke_family(record.family_id, now)
            self._fail("refresh", meta, reason="token_reuse", actor=record.user_id)
            raise Unauthorized(
                "Your session has ended. Please sign in again.", code="SESSION_REVOKED"
            )

        if _as_aware(record.expires_at, now) <= now:
            self._fail("refresh", meta, reason="expired", actor=record.user_id)
            raise Unauthorized(
                "Your session has ended. Please sign in again.", code="SESSION_EXPIRED"
            )

        user = self._users.get(record.user_id)
        if user is None or not user.is_active:
            self._tokens.revoke_family(record.family_id, now)
            self._fail("refresh", meta, reason="user_inactive", actor=record.user_id)
            raise Unauthorized(
                "Your session has ended. Please sign in again.", code="SESSION_EXPIRED"
            )

        issued, replacement = self._issue(user, meta, family_id=record.family_id)
        record.revoked_at = now
        record.replaced_by_id = replacement.id
        self._session.commit()
        AUTH_EVENTS.labels(event="refresh", outcome="success").inc()
        return issued

    def logout(
        self, *, refresh_token: str | None, user_id: uuid.UUID | None, meta: RequestMeta
    ) -> None:
        """Idempotent: signing out twice, or with an unknown token, is not an error."""
        if refresh_token:
            record = self._tokens.get_by_hash_for_update(hash_refresh_token(refresh_token))
            if record is not None:
                self._tokens.revoke_family(record.family_id, self._clock.now())
                user_id = user_id or record.user_id
        self._audit.record(
            action="auth.logout", outcome="success", meta=meta, actor_user_id=user_id
        )
        self._session.commit()
        AUTH_EVENTS.labels(event="logout", outcome="success").inc()

    # ── Internals ──────────────────────────────────────────────────────────

    def _start_session(self, user: User, meta: RequestMeta) -> IssuedSession:
        user.last_login_at = self._clock.now()
        issued, _ = self._issue(user, meta, family_id=uuid.uuid4())
        return issued

    def _issue(
        self, user: User, meta: RequestMeta, *, family_id: uuid.UUID
    ) -> tuple[IssuedSession, RefreshToken]:
        now = self._clock.now()
        access_token, access_expires_at = create_access_token(
            user_id=user.id, role=user.role, now=now, settings=self._settings
        )
        raw_refresh = new_refresh_token()
        refresh_expires_at = now + timedelta(days=self._settings.refresh_token_ttl_days)
        record = self._tokens.add(
            RefreshToken(
                user_id=user.id,
                family_id=family_id,
                token_hash=hash_refresh_token(raw_refresh),
                issued_at=now,
                expires_at=refresh_expires_at,
                ip_address=meta.ip_address,
                user_agent=(meta.user_agent or "")[:255] or None,
            )
        )
        return (
            IssuedSession(
                user=user,
                access_token=access_token,
                access_expires_at=access_expires_at,
                refresh_token=raw_refresh,
                refresh_expires_at=refresh_expires_at,
            ),
            record,
        )

    def _fail(
        self, event: str, meta: RequestMeta, *, reason: str, actor: uuid.UUID | None = None
    ) -> None:
        """Persist a failed attempt. Failures change no business data, so commit on their own."""
        self._audit.record(
            action=f"auth.{event}",
            outcome="failure",
            meta=meta,
            actor_user_id=actor,
            details={"reason": reason},
        )
        self._session.commit()
        AUTH_EVENTS.labels(event=event, outcome="failure").inc()
