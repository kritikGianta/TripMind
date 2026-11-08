"""Recent searches for signed-in travellers, so they can pick up where they left off.

Repeating a search moves it to the top instead of adding a duplicate. Only the newest
`history_keep` searches are kept per traveller, and a traveller can clear them at any time.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    delete,
    select,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin

log = logging.getLogger(__name__)
Vertical = Literal["flights", "hotels"]


class SearchHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "search_history"
    __table_args__ = (UniqueConstraint("user_id", "params_hash", name="uq_search_history_query"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vertical: Mapped[str] = mapped_column(String(8), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    params_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False)
    searched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SearchHistoryOut(BaseModel):
    id: uuid.UUID
    vertical: str
    params: dict[str, Any]
    label: str
    result_count: int
    searched_at: datetime


class SearchHistoryListOut(BaseModel):
    items: list[SearchHistoryOut]


def remember_search(
    session: Session,
    *,
    user_id: uuid.UUID,
    vertical: Vertical,
    params: dict[str, Any],
    label: str,
    result_count: int,
    at: datetime,
    keep: int,
) -> None:
    """Best effort: a failure here is logged and never breaks the search itself."""
    clean = {k: v for k, v in params.items() if v not in (None, [], ())}
    digest = hashlib.sha256(
        json.dumps({"v": vertical, **clean}, sort_keys=True, default=str).encode()
    ).hexdigest()
    try:
        row = session.scalar(
            select(SearchHistory).where(
                SearchHistory.user_id == user_id, SearchHistory.params_hash == digest
            )
        )
        if row is None:
            session.add(
                SearchHistory(
                    user_id=user_id,
                    vertical=vertical,
                    params=json.loads(json.dumps(clean, default=str)),
                    params_hash=digest,
                    label=label[:160],
                    result_count=result_count,
                    searched_at=at,
                )
            )
        else:
            row.searched_at, row.result_count, row.label = at, result_count, label[:160]
        session.flush()
        stale = list(
            session.scalars(
                select(SearchHistory.id)
                .where(SearchHistory.user_id == user_id)
                .order_by(SearchHistory.searched_at.desc())
                .offset(keep)
            )
        )
        if stale:
            session.execute(delete(SearchHistory).where(SearchHistory.id.in_(stale)))
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        log.warning("search history not recorded", exc_info=True)


def recent_searches(session: Session, user_id: uuid.UUID, limit: int = 20) -> SearchHistoryListOut:
    rows = session.scalars(
        select(SearchHistory)
        .where(SearchHistory.user_id == user_id)
        .order_by(SearchHistory.searched_at.desc())
        .limit(limit)
    )
    return SearchHistoryListOut(
        items=[
            SearchHistoryOut(
                id=r.id,
                vertical=r.vertical,
                params=r.params,
                label=r.label,
                result_count=r.result_count,
                searched_at=r.searched_at,
            )
            for r in rows
        ]
    )


def forget_searches(session: Session, user_id: uuid.UUID, search_id: uuid.UUID | None) -> int:
    query = delete(SearchHistory).where(SearchHistory.user_id == user_id)
    if search_id is not None:
        query = query.where(SearchHistory.id == search_id)
    removed = session.execute(query).rowcount  # type: ignore[attr-defined]
    session.commit()
    return int(removed or 0)
