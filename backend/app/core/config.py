"""Application settings.

Values come from environment variables (and `.env` during local development). Settings are
validated once at start-up so a misconfigured deployment fails fast instead of at first use.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_DEFAULT_SECRET = "dev-only-insecure-secret-change-me-before-any-deployment"  # noqa: S105
_REPO_ROOT = Path(__file__).resolve().parents[3]

Environment = Literal["local", "test", "staging", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Runtime
    app_name: str = "TripMind API"
    environment: Environment = "local"
    log_level: str = "INFO"
    log_json: bool = True
    api_prefix: str = "/api/v1"
    config_dir: Path = _REPO_ROOT / "config"

    # Database
    database_url: str = "postgresql+psycopg://tripmind:tripmind@127.0.0.1:5432/tripmind"
    db_pool_size: int = Field(default=10, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)
    db_echo: bool = False

    # Authentication
    jwt_secret: SecretStr = SecretStr(_INSECURE_DEFAULT_SECRET)
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_issuer: str = "tripmind"
    access_token_ttl_minutes: int = Field(default=15, ge=1, le=120)
    refresh_token_ttl_days: int = Field(default=7, ge=1, le=90)
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict"] = "lax"
    trust_proxy_headers: bool = True

    # Seeded demo accounts
    demo_traveler_email: str = "demo@tripmind.dev"
    demo_admin_email: str = "admin@tripmind.dev"

    # Shared state for several API replicas and the worker. Unset = in-process (one replica).
    redis_url: str | None = None
    worker_metrics_port: int = 9100
    # In-process background jobs (hold expiry). Off when the separate worker runs them.
    background_jobs: bool = True

    # Tracing is off unless an OTLP endpoint is configured (Compose `obs` profile sets it).
    otel_exporter_otlp_endpoint: str | None = None
    otel_service_name: str = "tripmind-api"

    # CORS is only needed for cross-origin callers; the web app uses a same-origin proxy.
    cors_origins: list[str] = Field(default_factory=list)

    # Sign-in protection and password reset.
    login_lockout_attempts: int = 8
    login_lockout_minutes: int = 15
    password_reset_minutes: int = 30
    # Largest JSON body accepted; dataset uploads have their own limit.
    max_request_mb: int = 2

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def auth_path(self) -> str:
        return f"{self.api_prefix}/auth"

    @model_validator(mode="after")
    def _guard_production(self) -> Settings:
        if self.environment in ("staging", "production"):
            secret = self.jwt_secret.get_secret_value()
            if secret == _INSECURE_DEFAULT_SECRET or len(secret) < 32:
                raise ValueError(
                    "JWT_SECRET must be set to a random value of at least 32 characters"
                )
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true outside local development")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
