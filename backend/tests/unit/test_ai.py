from __future__ import annotations

import json
from datetime import date

import httpx
import pytest

from app.modules.ai.knowledge import Chunk, KnowledgeBase
from app.modules.ai.llm import (
    AIConfig,
    LLMClient,
    ProviderConfig,
    extract_json,
    redact,
    reset_state_for_tests,
)
from app.modules.ai.nl_search import rule_parse

TODAY = date(2026, 11, 7)  # a Saturday


@pytest.fixture(autouse=True)
def _fresh_ai_state() -> None:
    reset_state_for_tests()


def test_redaction_removes_contact_and_card_details() -> None:
    text = "I'm asha@example.com, call +91 98765 43210, card 4242 4242 4242 4242, 2 adults"
    clean = redact(text)
    assert "asha@" not in clean and "98765" not in clean and "4242" not in clean
    assert "2 adults" in clean


def test_extract_json_tolerates_prose_and_fences() -> None:
    assert extract_json('Sure!\n```json\n{"a": {"b": "x}"}}\n```') == {"a": {"b": "x}"}}
    with pytest.raises(ValueError):
        extract_json("no json here")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "2 adults Delhi to Goa 20-24 Nov under 60k",
            {
                "adults": 2,
                "depart_date": date(2026, 11, 20),
                "return_date": date(2026, 11, 24),
                "max_budget": 60_000,
                "intent": "trip",
            },
        ),
        (
            "hotel in Jaipur for 3 nights from 2 dec, 4 star",
            {"intent": "stays", "nights": 3, "depart_date": date(2026, 12, 2), "min_stars": 4},
        ),
        (
            "cheapest flight to Mumbai tomorrow for a family of 4",
            {
                "intent": "flights",
                "adults": 4,
                "priority": "cheapest",
                "depart_date": date(2026, 11, 8),
            },
        ),
        (
            "business class next friday",
            {"cabin_class": "business", "depart_date": date(2026, 11, 13)},
        ),
        (
            "weekend getaway this weekend for a couple",
            {"adults": 2, "depart_date": date(2026, 11, 14), "return_date": date(2026, 11, 16)},
        ),
        ("trip on 5 jan budget 1.5 lakh", {"depart_date": date(2027, 1, 5), "max_budget": 150_000}),
    ],
)
def test_rule_parser(text: str, expected: dict[str, object]) -> None:
    parsed = rule_parse(text, TODAY)
    for key, value in expected.items():
        assert getattr(parsed, key) == value, key


def test_bm25_ranks_the_relevant_article_first() -> None:
    kb = KnowledgeBase(
        [
            Chunk("a", "Cancelling a flight", "Refund within 24 hours of booking.", "policy"),
            Chunk("b", "Loyalty points", "Earn one point per 100 paid.", "policy"),
            Chunk("c", "Searching for stays", "Choose a city and dates.", "docs"),
        ]
    )
    assert kb.search("how do I get a refund if I cancel my flight?")[0][0].id == "a"
    assert kb.search("points tier")[0][0].id == "b"
    assert kb.search("zzz") == []


def _client(handler: httpx.MockTransport, keys: dict[str, str | None]) -> LLMClient:
    config = AIConfig(
        order=["first", "second"],
        cooldown_seconds=60,
        providers={
            name: ProviderConfig(base_url=f"https://{name}.test/v1", model="m", key_env="X")
            for name in ("first", "second")
        },
    )
    return LLMClient(config, keys=keys, transport=handler)


def _reply(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_failover_cooldown_and_cache() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.host)
        if request.url.host == "first.test":
            return httpx.Response(429)
        body = json.loads(request.content)
        assert body["model"] == "m" and request.headers["authorization"] == "Bearer k2"
        return _reply('{"ok": true}')

    client = _client(httpx.MockTransport(handler), {"first": "k1", "second": "k2"})
    result = client.complete(feature="t", system="s", messages=[{"role": "user", "content": "q"}])
    assert result is not None and result.provider == "second"
    assert client.status()["first"] == "cooling_down"

    again = client.complete(feature="t", system="s", messages=[{"role": "user", "content": "q"}])
    assert again is not None and again.cached and calls == ["first.test", "second.test"]

    other = client.complete(feature="t", system="s", messages=[{"role": "user", "content": "x"}])
    assert other is not None and calls[-1] == "second.test"  # first is still cooling down


def test_no_keys_or_all_failing_returns_none() -> None:
    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout")

    assert (
        _client(httpx.MockTransport(broken), {"first": None, "second": None}).complete(
            feature="t", system="s", messages=[{"role": "user", "content": "q"}]
        )
        is None
    )
    assert (
        _client(httpx.MockTransport(broken), {"first": "k", "second": "k"}).complete(
            feature="t", system="s", messages=[{"role": "user", "content": "q"}]
        )
        is None
    )


def test_provider_receives_redacted_text() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.content.decode())
        return _reply("{}")

    _client(httpx.MockTransport(handler), {"first": "k", "second": None}).complete(
        feature="t", system="s", messages=[{"role": "user", "content": "mail me at a@b.com"}]
    )
    assert "a@b.com" not in seen[0] and "[email]" in seen[0]
