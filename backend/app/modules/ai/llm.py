"""Hosted LLM client with ordered failover, cooldowns, caching and redaction.

Every AI feature calls `LLMClient`; none talks to a provider directly. Guarantees:
- Providers are tried in configured order; one without a key is skipped, one that answers 429
  or fails is put on cooldown and the next is tried.
- Each call has a timeout. When nothing answers, the caller gets `None` and uses its rule-based
  fallback, so no traveller flow ever depends on an AI provider.
- Text is redacted (emails, phone and card-like numbers) before it leaves TripMind, because
  free tiers may use submitted content (plan v2, section 6).
- Identical requests are served from a short-lived cache to save free-tier quota.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeVar

import httpx
import structlog
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.kv import InMemoryStore, KeyValueStore
from app.core.metrics import AI_REQUESTS

log = structlog.get_logger(__name__)
T = TypeVar("T", bound=BaseModel)

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_LONG_NUMBER = re.compile(r"(?<!\d)(?:\+?\d[\d -]{8,}\d)(?!\d)")


def redact(text: str) -> str:
    """Remove contact details and card-like numbers before text is sent to a provider."""
    return _LONG_NUMBER.sub("[number]", _EMAIL.sub("[email]", text))


class ProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str
    model: str
    key_env: str
    json_mode: bool = True


class AIConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: list[str] = Field(default_factory=lambda: ["groq", "gemini", "openrouter"])
    timeout_seconds: float = 12
    cooldown_seconds: float = 60
    cache_ttl_seconds: float = 900
    max_output_tokens: int = 700
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)


@lru_cache(maxsize=4)
def _load(path: str, mtime: float) -> AIConfig:
    return AIConfig.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {})


def load_ai_config(config_dir: Path, order: str | None = None) -> AIConfig:
    path = config_dir / "ai.yaml"
    config = _load(str(path), path.stat().st_mtime) if path.exists() else AIConfig()
    if order:
        config = config.model_copy(update={"order": [p.strip() for p in order.split(",") if p]})
    return config


@dataclass(frozen=True)
class LLMResult:
    text: str
    provider: str
    cached: bool = False


def extract_json(text: str) -> Any:
    """The first JSON object in a reply (models sometimes wrap it in prose or fences)."""
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object in the reply")
    depth, in_string, escaped = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("unterminated JSON object")


# Default store for a single process; the API passes the shared (Redis) store when configured,
# so every replica sees the same cache and the same provider cooldowns.
_LOCAL_STORE = InMemoryStore()


class LLMClient:
    def __init__(
        self,
        config: AIConfig,
        keys: dict[str, str | None] | None = None,
        transport: httpx.BaseTransport | None = None,
        store: KeyValueStore | None = None,
    ) -> None:
        self._config = config
        self._store: KeyValueStore = store or _LOCAL_STORE
        self._keys = (
            keys
            if keys is not None
            else {name: os.environ.get(p.key_env) for name, p in config.providers.items()}
        )  # keys from the process environment when the caller does not pass them
        self._transport = transport

    def available(self) -> list[str]:
        return [n for n in self._config.order if n in self._config.providers and self._keys.get(n)]

    def _cooling(self, name: str) -> bool:
        return self._store.get(f"ai:cooldown:{name}") is not None

    def status(self) -> dict[str, str]:
        result = {}
        for name in self._config.order:
            if not self._keys.get(name):
                result[name] = "no_key"
            elif self._cooling(name):
                result[name] = "cooling_down"
            else:
                result[name] = "ready"
        return result

    def complete(
        self, *, feature: str, system: str, messages: list[dict[str, str]], json_mode: bool = False
    ) -> LLMResult | None:
        messages = [{"role": m["role"], "content": redact(m["content"])} for m in messages]
        key = hashlib.sha256(
            json.dumps([feature, system, messages, json_mode]).encode()
        ).hexdigest()
        cached = self._store.get(f"ai:cache:{key}")
        if cached is not None:
            hit = json.loads(cached)
            AI_REQUESTS.labels(provider=hit["provider"], feature=feature, outcome="cached").inc()
            return LLMResult(hit["text"], hit["provider"], cached=True)

        for name in self.available():
            if self._cooling(name):
                continue
            result = self._call(name, feature, system, messages, json_mode)
            if result is not None:
                self._store.set(
                    f"ai:cache:{key}",
                    json.dumps({"text": result.text, "provider": result.provider}),
                    self._config.cache_ttl_seconds,
                )
                return result
        return None

    def complete_json(
        self, *, feature: str, system: str, user: str, schema: type[T]
    ) -> tuple[T, str] | None:
        """A reply validated against `schema`; providers with invalid output are skipped."""
        result = self.complete(
            feature=feature,
            system=system,
            messages=[{"role": "user", "content": user}],
            json_mode=True,
        )
        if result is None:
            return None
        try:
            return schema.model_validate(extract_json(result.text)), result.provider
        except (ValueError, ValidationError) as exc:
            AI_REQUESTS.labels(
                provider=result.provider, feature=feature, outcome="invalid_output"
            ).inc()
            log.warning(
                "ai_invalid_output",
                provider=result.provider,
                feature=feature,
                error=type(exc).__name__,
            )
            return None

    def _call(
        self, name: str, feature: str, system: str, messages: list[dict[str, str]], json_mode: bool
    ) -> LLMResult | None:
        provider = self._config.providers[name]
        body: dict[str, Any] = {
            "model": provider.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": 0.2,
            "max_tokens": self._config.max_output_tokens,
        }
        if json_mode and provider.json_mode:
            body["response_format"] = {"type": "json_object"}
        started = time.perf_counter()
        try:
            with httpx.Client(
                timeout=self._config.timeout_seconds, transport=self._transport
            ) as client:
                response = client.post(
                    f"{provider.base_url}/chat/completions",
                    json=body,
                    headers={"Authorization": f"Bearer {self._keys[name]}", "X-Title": "TripMind"},
                )
            if response.status_code == 429 or response.status_code >= 500:
                self._cool_down(
                    name, feature, "rate_limited" if response.status_code == 429 else "server_error"
                )
                return None
            response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"] or ""
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            self._cool_down(name, feature, "error")
            log.warning(
                "ai_provider_failed", provider=name, feature=feature, error=type(exc).__name__
            )
            return None
        AI_REQUESTS.labels(provider=name, feature=feature, outcome="ok").inc()
        log.info(
            "ai_call",
            provider=name,
            feature=feature,
            ms=int((time.perf_counter() - started) * 1000),
        )
        return LLMResult(text=text, provider=name)

    def _cool_down(self, name: str, feature: str, outcome: str) -> None:
        AI_REQUESTS.labels(provider=name, feature=feature, outcome=outcome).inc()
        self._store.set(f"ai:cooldown:{name}", outcome, self._config.cooldown_seconds)


def reset_state_for_tests() -> None:
    _LOCAL_STORE.clear()
