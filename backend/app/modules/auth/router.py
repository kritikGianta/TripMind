"""Auth HTTP endpoints. Thin: validate input, call one service method, shape the response."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.deps import (
    get_clock,
    get_request_meta,
    get_settings_dep,
    rate_limit,
    require_feature,
)
from app.core.errors import ErrorEnvelope
from app.core.request_context import RequestMeta
from app.db.session import get_session
from app.modules.auth.cookies import REFRESH_COOKIE, clear_session_cookies, set_session_cookies
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User, UserRole
from app.modules.auth.schemas import (
    DemoLoginRequest,
    LoginRequest,
    RegisterRequest,
    SessionOut,
    UserOut,
)
from app.modules.auth.service import AuthService, IssuedSession

router = APIRouter(prefix="/auth", tags=["auth"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorEnvelope},
    409: {"model": ErrorEnvelope},
    422: {"model": ErrorEnvelope},
    429: {"model": ErrorEnvelope},
}


def get_auth_service(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> AuthService:
    return AuthService(session, settings, clock)


def _session_response(
    response: Response, issued: IssuedSession, settings: Settings, clock: Clock
) -> SessionOut:
    set_session_cookies(
        response,
        access_token=issued.access_token,
        access_expires_at=issued.access_expires_at,
        refresh_token=issued.refresh_token,
        refresh_expires_at=issued.refresh_expires_at,
        now=clock.now(),
        settings=settings,
    )
    response.headers["Cache-Control"] = "no-store"
    return SessionOut(
        user=UserOut.model_validate(issued.user), access_expires_at=issued.access_expires_at
    )


@router.post(
    "/register",
    response_model=SessionOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    dependencies=[
        Depends(require_feature("registration")),
        Depends(rate_limit("register", limit=5, window_seconds=60)),
    ],
    summary="Create a traveller account and start a session",
)
def register(
    body: RegisterRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
    meta: RequestMeta = Depends(get_request_meta),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> SessionOut:
    issued = service.register(
        email=str(body.email), password=body.password, full_name=body.full_name, meta=meta
    )
    return _session_response(response, issued, settings, clock)


@router.post(
    "/login",
    response_model=SessionOut,
    responses=_ERRORS,
    dependencies=[Depends(rate_limit("login", limit=10, window_seconds=60))],
    summary="Sign in with email and password",
)
def login(
    body: LoginRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
    meta: RequestMeta = Depends(get_request_meta),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> SessionOut:
    issued = service.login(email=str(body.email), password=body.password, meta=meta)
    return _session_response(response, issued, settings, clock)


@router.post(
    "/demo-login",
    response_model=SessionOut,
    responses=_ERRORS,
    dependencies=[
        Depends(require_feature("demo_login")),
        Depends(rate_limit("demo_login", limit=20, window_seconds=60)),
    ],
    summary="Sign in as a seeded demo account (disabled in production)",
)
def demo_login(
    body: DemoLoginRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
    meta: RequestMeta = Depends(get_request_meta),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> SessionOut:
    issued = service.demo_login(role=UserRole(body.role), meta=meta)
    return _session_response(response, issued, settings, clock)


@router.post(
    "/refresh",
    response_model=SessionOut,
    responses=_ERRORS,
    dependencies=[Depends(rate_limit("refresh", limit=60, window_seconds=60))],
    summary="Rotate the refresh token and issue a new access token",
)
def refresh(
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
    meta: RequestMeta = Depends(get_request_meta),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> SessionOut:
    try:
        issued = service.refresh(refresh_token=request.cookies.get(REFRESH_COOKIE), meta=meta)
    except Exception:
        clear_session_cookies(response, settings)
        raise
    return _session_response(response, issued, settings, clock)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="End the current session",
)
def logout(
    request: Request,
    service: AuthService = Depends(get_auth_service),
    meta: RequestMeta = Depends(get_request_meta),
    settings: Settings = Depends(get_settings_dep),
) -> Response:
    service.logout(refresh_token=request.cookies.get(REFRESH_COOKIE), user_id=None, meta=meta)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookies(response, settings)
    return response


@router.get(
    "/me",
    response_model=UserOut,
    responses={401: {"model": ErrorEnvelope}},
    summary="The signed-in user",
)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
