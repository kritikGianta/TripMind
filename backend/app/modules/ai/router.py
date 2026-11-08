"""AI endpoints. Each answers with or without a hosted model (see `source` in responses)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.deps import (
    get_clock,
    get_kv_store,
    get_settings_dep,
    rate_limit,
    require_feature,
)
from app.core.errors import DomainError, ErrorEnvelope
from app.core.kv import KeyValueStore
from app.db.session import get_session
from app.modules.ai.assistant import Assistant, AssistantOut, AssistantRequest
from app.modules.ai.knowledge import knowledge_base
from app.modules.ai.llm import LLMClient, load_ai_config
from app.modules.ai.nl_search import NaturalLanguageSearch, ParsedSearchOut
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.vocabulary import load_vocabulary

router = APIRouter(prefix="/ai", tags=["ai"])
_ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorEnvelope},
    422: {"model": ErrorEnvelope},
    429: {"model": ErrorEnvelope},
}


def get_llm(
    settings: Settings = Depends(get_settings_dep), store: KeyValueStore = Depends(get_kv_store)
) -> LLMClient:
    """Composition point: tests override this with a fake or a mocked transport."""
    keys = {
        "groq": settings.groq_api_key,
        "gemini": settings.gemini_api_key,
        "openrouter": settings.openrouter_api_key,
    }
    return LLMClient(
        load_ai_config(settings.config_dir, settings.llm_provider_order),
        keys={name: key.get_secret_value() if key else None for name, key in keys.items()},
        store=store,
    )


def optional_user(
    request: Request,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> User | None:
    try:
        return get_current_user(request, session, settings, clock)
    except DomainError:
        return None


class StatusOut(BaseModel):
    providers: dict[str, str]
    active_provider: str | None


class ParseIn(BaseModel):
    text: str = Field(min_length=3, max_length=300)


@router.get("/status", response_model=StatusOut, summary="Which AI providers are configured")
def status(llm: LLMClient = Depends(get_llm)) -> StatusOut:
    providers = llm.status()
    return StatusOut(
        providers=providers,
        active_provider=next((n for n, s in providers.items() if s == "ready"), None),
    )


@router.post(
    "/parse-search",
    response_model=ParsedSearchOut,
    responses=_ERRORS,
    dependencies=[
        Depends(require_feature("ai_search")),
        Depends(rate_limit("ai.parse", limit=20, window_seconds=60)),
    ],
    summary="Turn a sentence into search criteria (LLM, or rules as fallback)",
)
def parse_search(
    body: ParseIn,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
    llm: LLMClient = Depends(get_llm),
) -> ParsedSearchOut:
    window = CatalogRepository(session).flight_window()
    service = NaturalLanguageSearch(
        session,
        llm,
        load_vocabulary(settings.config_dir),
        today=(clock.now() - timedelta(hours=12)).date(),
        window=(window[0].date(), window[1].date()) if window else None,
    )
    return service.parse(body.text)


@router.post(
    "/assistant",
    response_model=AssistantOut,
    responses=_ERRORS,
    dependencies=[
        Depends(require_feature("ai_assistant")),
        Depends(rate_limit("ai.assistant", limit=20, window_seconds=60)),
    ],
    summary="Ask the help assistant (grounded in TripMind help and your trips)",
)
def assistant(
    body: AssistantRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    llm: LLMClient = Depends(get_llm),
    user: User | None = Depends(optional_user),
) -> AssistantOut:
    return Assistant(session, llm, knowledge_base(settings.config_dir)).answer(body, user)
