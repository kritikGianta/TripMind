from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.auth.models import RefreshToken, User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: uuid.UUID) -> User | None:
        return self._session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self._session.scalar(select(User).where(User.email == email.lower()))

    def add(self, user: User) -> User:
        self._session.add(user)
        self._session.flush()
        return user


class RefreshTokenRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, token: RefreshToken) -> RefreshToken:
        self._session.add(token)
        self._session.flush()
        return token

    def get_by_hash_for_update(self, token_hash: str) -> RefreshToken | None:
        # Row lock serialises concurrent refreshes of the same token (ignored by SQLite).
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
        return self._session.scalar(stmt)

    def revoke_family(self, family_id: uuid.UUID, at: datetime) -> int:
        result = self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=at)
        )
        return int(result.rowcount or 0)  # type: ignore[attr-defined]
