from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.deps import get_clock
from app.db.session import get_session
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.notifications.service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    id: uuid.UUID
    kind: str
    severity: str
    title: str
    body: str
    link: str | None
    created_at: datetime
    read: bool
    emailed: bool


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    unread: int


@router.get("", response_model=NotificationListOut, summary="My latest notifications")
def list_notifications(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
) -> NotificationListOut:
    items, unread = NotificationService(session).recent(user.id)
    return NotificationListOut(
        items=[
            NotificationOut(
                id=n.id,
                kind=n.kind,
                severity=n.severity,
                title=n.title,
                body=n.body,
                link=n.link,
                created_at=n.created_at,
                read=n.read_at is not None,
                emailed=n.emailed_at is not None,
            )
            for n in items
        ],
        unread=unread,
    )


@router.post(
    "/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark one notification (or all, without an ID) as read",
)
def mark_read(
    notification_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
) -> None:
    NotificationService(session).mark_read(user.id, clock.now(), notification_id)
