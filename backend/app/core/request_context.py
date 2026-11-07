"""Per-request context shared by logging, error handling and audit records."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


@dataclass(frozen=True)
class RequestMeta:
    """Who and where a request came from, captured at the HTTP edge."""

    ip_address: str | None
    user_agent: str | None


def get_request_id() -> str | None:
    return _request_id.get()


def set_request_id(value: str | None) -> Token[str | None]:
    return _request_id.set(value)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id.reset(token)
