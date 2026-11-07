from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.features import load_feature_flags
from app.core.rate_limit import InMemoryRateLimiter


def test_production_refuses_default_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None, environment="production", cookie_secure=True)


def test_production_requires_secure_cookies() -> None:
    with pytest.raises(ValidationError, match="COOKIE_SECURE"):
        Settings(_env_file=None, environment="production", jwt_secret="z" * 64)  # type: ignore[arg-type]


def _flags_file(tmp_path: Path, body: str) -> Path:
    (tmp_path / "features.yaml").write_text(body, encoding="utf-8")
    return tmp_path


def test_feature_flags_read_yaml_and_env_override(tmp_path: Path) -> None:
    config_dir = _flags_file(tmp_path, "features:\n  demo_login: true\n  registration: true\n")
    settings = Settings(_env_file=None, environment="test", config_dir=config_dir)
    flags = load_feature_flags(settings, environ={"FEATURE_REGISTRATION": "false"})
    assert flags.enabled("demo_login") is True
    assert flags.enabled("registration") is False
    assert flags.enabled("not_declared") is False


def test_invalid_flag_override_fails_fast(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        environment="test",
        config_dir=_flags_file(tmp_path, "features:\n  x: true\n"),
    )
    with pytest.raises(ValueError, match="FEATURE_X"):
        load_feature_flags(settings, environ={"FEATURE_X": "maybe"})


def test_demo_login_cannot_run_in_production(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        jwt_secret="z" * 64,  # type: ignore[arg-type]
        cookie_secure=True,
        config_dir=_flags_file(tmp_path, "features:\n  demo_login: true\n"),
    )
    with pytest.raises(ValueError, match="demo_login"):
        load_feature_flags(settings, environ={})


def test_rate_limiter_sliding_window() -> None:
    now = [0.0]
    limiter = InMemoryRateLimiter(monotonic=lambda: now[0])
    assert all(limiter.hit("k", limit=3, window_seconds=10)[0] for _ in range(3))
    allowed, retry_after = limiter.hit("k", limit=3, window_seconds=10)
    assert allowed is False and retry_after >= 1
    now[0] = 10.5
    assert limiter.hit("k", limit=3, window_seconds=10)[0] is True
    assert limiter.hit("other", limit=3, window_seconds=10)[0] is True
