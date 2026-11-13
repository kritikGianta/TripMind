"""Auth HTTP endpoints. Thin: validate input, call one service method, shape the response."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.deps import (
    get_clock,
    get_kv_store,
    get_request_meta,
    get_settings_dep,
    rate_limit,
    require_feature,
)
from app.core.errors import ErrorEnvelope
from app.core.kv import KeyValueStore
from app.core.request_context import RequestMeta
from app.db.session import get_session
from app.modules.auth.cookies import REFRESH_COOKIE, clear_session_cookies, set_session_cookies
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User, UserRole
from app.modules.auth.schemas import (
    DemoLoginRequest,
    LoginRequest,
    PasswordChange,
    PasswordForgot,
    PasswordForgotOut,
    PasswordReset,
    ProfileUpdate,
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
    store: KeyValueStore = Depends(get_kv_store),
) -> AuthService:
    return AuthService(session, settings, clock, store)


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
    "/guest",
    response_model=SessionOut,
    responses=_ERRORS,
    dependencies=[
        Depends(require_feature("guest_access")),
        Depends(rate_limit("guest", limit=30, window_seconds=60)),
    ],
    summary="Start a private guest session: no sign-up, no password",
)
def guest_login(
    response: Response,
    service: AuthService = Depends(get_auth_service),
    meta: RequestMeta = Depends(get_request_meta),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> SessionOut:
    issued = service.guest_login(meta=meta)
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


@router.patch("/me", response_model=UserOut, responses=_ERRORS, summary="Update my profile")
def update_me(
    body: ProfileUpdate,
    user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
    meta: RequestMeta = Depends(get_request_meta),
) -> UserOut:
    return UserOut.model_validate(service.update_profile(user, body.full_name, meta))


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORS,
    summary="Sign out on every device",
)
def logout_all(
    user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
    meta: RequestMeta = Depends(get_request_meta),
    settings: Settings = Depends(get_settings_dep),
) -> Response:
    service.logout_everywhere(user, meta)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookies(response, settings)
    return response


@router.post(
    "/password",
    response_model=SessionOut,
    responses=_ERRORS,
    dependencies=[Depends(rate_limit("password_change", limit=10, window_seconds=300))],
    summary="Change my password; other devices are signed out",
)
def change_password(
    body: PasswordChange,
    response: Response,
    user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
    meta: RequestMeta = Depends(get_request_meta),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> SessionOut:
    issued = service.change_password(user, body.current_password, body.new_password, meta)
    return _session_response(response, issued, settings, clock)


@router.post(
    "/password/forgot",
    response_model=PasswordForgotOut,
    status_code=status.HTTP_202_ACCEPTED,
    responses=_ERRORS,
    dependencies=[Depends(rate_limit("password_forgot", limit=5, window_seconds=300))],
    summary="Request a password reset (same answer whether or not the account exists)",
)
def forgot_password(
    body: PasswordForgot,
    service: AuthService = Depends(get_auth_service),
    meta: RequestMeta = Depends(get_request_meta),
) -> PasswordForgotOut:
    token = service.forgot_password(str(body.email), meta)
    return PasswordForgotOut(
        message="If that address has an account, a reset link is on its way.",
        dev_reset_token=token,
    )


@router.post(
    "/password/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORS,
    dependencies=[Depends(rate_limit("password_reset", limit=10, window_seconds=300))],
    summary="Set a new password with a reset token; every session ends",
)
def reset_password(
    body: PasswordReset,
    service: AuthService = Depends(get_auth_service),
    meta: RequestMeta = Depends(get_request_meta),
) -> None:
    service.reset_password(body.token, body.new_password, meta)
