"""Notifications: written in the caller's transaction, so a message exists exactly when the
change it describes was committed. The email channel is simulated: it is logged, not sent."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.modules.notifications.models import Notification

log = structlog.get_logger(__name__)

Severity = Literal["info", "success", "warning", "critical"]


class NotificationService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def notify(
        self,
        *,
        user_id: uuid.UUID,
        kind: str,
        title: str,
        body: str,
        now: datetime,
        link: str | None = None,
        severity: Severity = "info",
        email: bool = True,
    ) -> None:
        self._session.add(
            Notification(
                user_id=user_id,
                kind=kind,
                severity=severity,
                title=title[:160],
                body=body[:600],
                link=link,
                created_at=now,
                emailed_at=now if email else None,
            )
        )
        if email:
            # Simulated delivery: the event is logged with the user ID, never the address.
            log.info("email_simulated", user_id=str(user_id), kind=kind, title=title)

    def recent(self, user_id: uuid.UUID, limit: int = 30) -> tuple[list[Notification], int]:
        items = list(
            self._session.scalars(
                select(Notification)
                .where(Notification.user_id == user_id)
                .order_by(Notification.created_at.desc())
                .limit(limit)
            )
        )
        unread = int(
            self._session.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            )
            or 0
        )
        return items, unread

    def mark_read(
        self, user_id: uuid.UUID, now: datetime, notification_id: uuid.UUID | None = None
    ) -> None:
        query = update(Notification).where(
            Notification.user_id == user_id, Notification.read_at.is_(None)
        )
        if notification_id is not None:
            query = query.where(Notification.id == notification_id)
        self._session.execute(query.values(read_at=now))
        self._session.commit()
