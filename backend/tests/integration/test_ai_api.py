"""AI endpoints with no provider (rules) and with a mocked provider."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from app.cli import seed
from app.modules.ai.llm import AIConfig, LLMClient, ProviderConfig, reset_state_for_tests
from app.modules.ai.router import get_llm

API = "/api/v1"


@pytest.fixture(autouse=True)
def _fresh_ai_state() -> Iterator[None]:
    reset_state_for_tests()
    yield
    reset_state_for_tests()


def use_provider(
    client: TestClient, reply: Callable[[dict[str, object]], str], seen: list[dict[str, object]]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        return httpx.Response(200, json={"choices": [{"message": {"content": reply(body)}}]})

    config = AIConfig(
        order=["mock"],
        providers={"mock": ProviderConfig(base_url="https://mock.test/v1", model="m", key_env="X")},
    )
    llm = LLMClient(config, keys={"mock": "k"}, transport=httpx.MockTransport(handler))
    client.app.dependency_overrides[get_llm] = lambda: llm  # type: ignore[attr-defined]


def test_parse_search_without_ai_uses_rules_and_the_catalog(
    client: TestClient, catalog: None
) -> None:
    status = client.get(f"{API}/ai/status").json()
    assert status["active_provider"] is None  # tests run without keys
    parsed = client.post(
        f"{API}/ai/parse-search",
        json={"text": "2 of us from Bombay to Bangalore on 14 Nov, back 16 Nov"},
    )
    assert parsed.status_code == 200, parsed.text
    body = parsed.json()
    assert body["source"] == "rules"
    assert body["origin"]["label"] == "Mumbai" and body["origin"]["airport_code"] == "BOM"
    assert body["destination"]["label"] == "Bengaluru"
    assert body["adults"] == 2 and body["depart_date"] == "2026-11-14"
    assert body["return_date"] == "2026-11-16" and body["missing"] == []


def test_parse_search_with_a_provider_is_grounded_in_the_catalog(
    client: TestClient, catalog: None
) -> None:
    seen: list[dict[str, object]] = []
    use_provider(
        client,
        lambda _: json.dumps(
            {
                "intent": "trip",
                "origin": "Delhi",
                "destination": "Atlantis",
                "depart_date": "2026-11-20",
                "nights": 3,
                "adults": 2,
            }
        ),
        seen,
    )
    body = client.post(
        f"{API}/ai/parse-search", json={"text": "Delhi to Atlantis next friday for 3 nights"}
    ).json()
    assert body["source"] == "ai:mock"
    assert body["origin"]["label"] == "Delhi"
    assert body["destination"] is None and body["unknown_places"] == ["Atlantis"]
    assert body["return_date"] == "2026-11-23" and "destination" in body["missing"]
    assert seen[0]["response_format"] == {"type": "json_object"}


def test_assistant_falls_back_to_help_articles(client: TestClient, catalog: None) -> None:
    answer = client.post(
        f"{API}/ai/assistant",
        json={"messages": [{"role": "user", "content": "How long are seats held while I pay?"}]},
    ).json()
    assert answer["source"] == "rules"
    assert answer["citations"][0]["title"] == "Holds and payment"
    assert "15 minutes" in answer["answer"]  # generated from config/rules.yaml


def test_assistant_with_provider_uses_trips_without_personal_data(
    client: TestClient, catalog: None
) -> None:
    seed()
    client.post(f"{API}/auth/demo-login", json={"role": "traveler"})
    seen: list[dict[str, object]] = []
    use_provider(
        client,
        lambda _: json.dumps(
            {
                "answer": "You can cancel within 24 hours for a full refund.",
                "sources": [1, 9],
                "actions": [
                    {"label": "My Trips", "href": "/trips"},
                    {"label": "Evil", "href": "https://evil.example"},
                ],
            }
        ),
        seen,
    )
    answer = client.post(
        f"{API}/ai/assistant",
        json={
            "messages": [
                {"role": "user", "content": "Can I cancel my flight? My email is demo@tripmind.dev"}
            ]
        },
    ).json()
    assert answer["source"] == "ai:mock"
    assert len(answer["citations"]) == 1  # out-of-range source numbers are dropped
    assert answer["actions"] == [{"label": "My Trips", "href": "/trips"}]  # external link removed
    sent = json.dumps(seen[0])
    assert "demo@tripmind.dev" not in sent and "Demo Traveller" not in sent
    assert "Cancelling a flight" in sent  # the grounding article was supplied


def test_ai_features_can_be_switched_off(client: TestClient) -> None:
    from app.core.deps import get_feature_flags
    from app.core.features import FeatureFlags

    client.app.dependency_overrides[get_feature_flags] = lambda: FeatureFlags(  # type: ignore[attr-defined]
        {"ai_search": False, "ai_assistant": False}
    )
    response = client.post(f"{API}/ai/parse-search", json={"text": "Goa next week"})
    assert response.status_code == 404 and response.json()["error"]["code"] == "FEATURE_DISABLED"
