"""Audit recording.

The audit row is added to the caller's session so it commits (or rolls back) atomically with the
business change it describes. Failed sign-ins have no business change, so callers commit them
explicitly.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.request_context import RequestMeta, get_request_id
from app.modules.audit.models import AuditLog


class AuditService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        *,
        action: str,
        outcome: str,
        meta: RequestMeta,
        actor_user_id: uuid.UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self._session.add(
            AuditLog(
                actor_user_id=actor_user_id,
                action=action,
                outcome=outcome,
                request_id=get_request_id(),
                ip_address=meta.ip_address,
                user_agent=(meta.user_agent or "")[:255] or None,
                details=details,
            )
        )
