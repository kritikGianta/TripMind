"""Authentication use cases.

Each public method is one use case and owns its transaction: it either commits all of its changes
(including the audit record) or none of them.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import (
    Conflict,
    Forbidden,
    NotFound,
    RateLimited,
    Unauthorized,
    ValidationFailed,
)
from app.core.kv import InMemoryStore, KeyValueStore
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
from app.modules.auth.models import (
    GUEST_EMAIL_DOMAIN,
    PasswordResetToken,
    RefreshToken,
    User,
    UserRole,
)
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
    def __init__(
        self,
        session: Session,
        settings: Settings,
        clock: Clock,
        store: KeyValueStore | None = None,
    ) -> None:
        self._session = session
        self._store = store or InMemoryStore()
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

    def _lock_key(self, email: str) -> str:
        return "auth:" + hashlib.sha256(email.lower().encode()).hexdigest()[:32]

    def _record_failed_login(self, email: str) -> None:
        """Lock an address after repeated failures; unknown addresses behave the same, so the
        lock does not reveal which accounts exist."""
        minutes = self._settings.login_lockout_minutes
        allowed, _ = self._store.window_hit(
            self._lock_key(email) + ":fails",
            limit=self._settings.login_lockout_attempts - 1,  # refused on the Nth failure
            window_seconds=minutes * 60,
        )
        if not allowed:
            self._store.set(self._lock_key(email) + ":locked", "1", minutes * 60)

    def login(self, *, email: str, password: str, meta: RequestMeta) -> IssuedSession:
        if self._store.get(self._lock_key(email) + ":locked"):
            self._fail("login", meta, reason="locked")
            raise RateLimited(
                "Too many failed sign-ins. Try again later or reset your password.",
                code="ACCOUNT_LOCKED",
                headers={"Retry-After": str(self._settings.login_lockout_minutes * 60)},
            )
        user = self._users.get_by_email(email)
        if user is None:
            burn_password_check(password)
            self._record_failed_login(email)
            self._fail("login", meta, reason="unknown_email")
            raise Unauthorized("Email or password is incorrect.", code="INVALID_CREDENTIALS")

        valid, upgraded_hash = verify_password(password, user.password_hash)
        if not valid:
            self._record_failed_login(email)
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

    def guest_login(self, *, meta: RequestMeta) -> IssuedSession:
        """Start a session for a new, private guest traveller.

        The website calls this on a first visit, so nobody has to sign up or sign in. A guest has
        an unusable random password (it can never be signed into by password), and everything it
        does (bookings, reservations, groups, alerts) belongs to it alone.
        """
        user = User(
            email=f"guest-{secrets.token_hex(8)}{GUEST_EMAIL_DOMAIN}",
            full_name="Guest traveller",
            password_hash=hash_password(secrets.token_urlsafe(32)),
            role=UserRole.TRAVELER,
        )
        self._users.add(user)
        issued = self._start_session(user, meta)
        self._audit.record(
            action="auth.guest", outcome="success", meta=meta, actor_user_id=user.id
        )
        self._session.commit()
        AUTH_EVENTS.labels(event="guest", outcome="success").inc()
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

    def logout_everywhere(self, user: User, meta: RequestMeta) -> None:
        self._tokens.revoke_all_for_user(user.id, self._clock.now())
        self._audit.record(
            action="auth.logout_all", outcome="success", meta=meta, actor_user_id=user.id
        )
        self._session.commit()

    def update_profile(self, user: User, full_name: str, meta: RequestMeta) -> User:
        user.full_name = full_name
        self._audit.record(
            action="auth.profile_updated", outcome="success", meta=meta, actor_user_id=user.id
        )
        self._session.commit()
        return user

    def change_password(
        self, user: User, current: str, new: str, meta: RequestMeta
    ) -> IssuedSession:
        """Every other session ends; this device gets a fresh one."""
        valid, _ = verify_password(current, user.password_hash)
        if not valid:
            self._fail("password_change", meta, reason="wrong_password", actor=user.id)
            raise ValidationFailed("Your current password is incorrect.", code="WRONG_PASSWORD")
        user.password_hash = hash_password(new)
        self._tokens.revoke_all_for_user(user.id, self._clock.now())
        issued = self._start_session(user, meta)
        self._audit.record(
            action="auth.password_changed", outcome="success", meta=meta, actor_user_id=user.id
        )
        self._session.commit()
        return issued

    def forgot_password(self, email: str, meta: RequestMeta) -> str | None:
        """The answer is the same whether or not the account exists. Email is simulated."""
        user = self._users.get_by_email(email)
        token = None
        if user is not None and user.is_active:
            token = secrets.token_urlsafe(32)
            self._session.add(
                PasswordResetToken(
                    user_id=user.id,
                    token_hash=hash_refresh_token(token),
                    expires_at=self._clock.now()
                    + timedelta(minutes=self._settings.password_reset_minutes),
                )
            )
        self._audit.record(
            action="auth.password_reset_requested",
            outcome="success",
            meta=meta,
            actor_user_id=user.id if user else None,
        )
        self._session.commit()
        return token if self._settings.environment in ("local", "test") else None

    def reset_password(self, token: str, new: str, meta: RequestMeta) -> None:
        now = self._clock.now()
        record = self._session.scalar(
            select(PasswordResetToken)
            .where(PasswordResetToken.token_hash == hash_refresh_token(token))
            .with_for_update()
        )
        user = self._users.get(record.user_id) if record else None
        if (
            record is None
            or user is None
            or record.used_at is not None
            or _as_aware(record.expires_at, now) <= now
        ):
            self._fail("password_reset", meta, reason="invalid_token")
            raise ValidationFailed(
                "This reset link is invalid or has expired.", code="RESET_TOKEN_INVALID"
            )
        record.used_at = now
        user.password_hash = hash_password(new)
        self._tokens.revoke_all_for_user(user.id, now)
        self._store.delete(self._lock_key(user.email) + ":locked")
        self._audit.record(
            action="auth.password_reset", outcome="success", meta=meta, actor_user_id=user.id
        )
        self._session.commit()

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
