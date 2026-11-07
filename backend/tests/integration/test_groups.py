"""Group planning: share a plan, join, vote, budgets, consensus, decide."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.cli import seed

API = "/api/v1"


def register(client: TestClient, email: str, name: str) -> None:
    client.post(f"{API}/auth/logout")
    response = client.post(
        f"{API}/auth/register",
        json={"email": email, "password": "a-long-passphrase", "full_name": name},
    )
    if response.status_code == 409:
        client.post(f"{API}/auth/login", json={"email": email, "password": "a-long-passphrase"})


@pytest.fixture
def shared(client: TestClient, catalog: None) -> dict[str, Any]:
    """Asha plans a trip to Mumbai and shares it; returns the group as Asha sees it."""
    seed()
    register(client, "asha@example.com", "Asha Rao")
    city = client.get(f"{API}/locations", params={"q": "Mumbai", "kind": "city"}).json()
    plan = client.post(
        f"{API}/plans",
        json={
            "origin": "DEL",
            "destination_city_id": city["items"][0]["value"],
            "depart_date": "2026-11-13",
            "return_date": "2026-11-15",
            "adults": 2,
        },
    ).json()
    group = client.post(f"{API}/plans/{plan['id']}/group")
    assert group.status_code == 201, group.text
    return dict(group.json())


def test_share_join_vote_and_decide(client: TestClient, shared: dict[str, Any]) -> None:
    code, group_id = shared["invite_code"], shared["id"]
    first, second = shared["options"][0]["option"]["id"], shared["options"][1]["option"]["id"]
    assert shared["is_owner"] and shared["consensus"].startswith("Nobody has voted")

    # Sharing the same plan again returns the same group.
    again = client.post(f"{API}/plans/{shared['plan_id']}/group").json()
    assert again["id"] == group_id

    client.put(f"{API}/groups/{group_id}/votes/{first}", json={"vote": "no"})
    client.put(f"{API}/groups/{group_id}/votes/{second}", json={"vote": "love"})

    register(client, "ravi@example.com", "Ravi Mehta")
    assert client.get(f"{API}/groups/{group_id}").status_code == 404  # not a member yet
    joined = client.post(f"{API}/groups/join", json={"invite_code": code}).json()
    assert len(joined["members"]) == 2 and not joined["is_owner"]
    view = client.put(f"{API}/groups/{group_id}/votes/{second}", json={"vote": "ok"}).json()
    assert view["leader_option_id"] == second
    leader = next(o for o in view["options"] if o["option"]["id"] == second)
    assert (leader["love"], leader["ok"], leader["no"]) == (1, 1, 0)
    assert "No vetoes" in view["consensus"]
    vetoed = next(o for o in view["options"] if o["option"]["id"] == first)
    assert vetoed["no"] == 1 and vetoed["position"] > 1

    assert (
        client.post(f"{API}/groups/{group_id}/decide", json={"option_id": second}).status_code
        == 403
    )  # only the owner decides
    register(client, "asha@example.com", "Asha Rao")
    decided = client.post(f"{API}/groups/{group_id}/decide", json={"option_id": second}).json()
    assert decided["status"] == "decided" and decided["decided_option_id"] == second
    closed = client.put(f"{API}/groups/{group_id}/votes/{first}", json={"vote": "ok"})
    assert closed.status_code == 409


def test_budgets_shape_the_consensus(client: TestClient, shared: dict[str, Any]) -> None:
    group_id = shared["id"]
    cheapest = min(o["per_person"]["amount_minor"] for o in shared["options"]) // 100
    view = client.put(
        f"{API}/groups/{group_id}/me", json={"max_budget_per_person": cheapest}
    ).json()
    leader = next(o for o in view["options"] if o["option"]["id"] == view["leader_option_id"])
    assert leader["per_person"]["amount_minor"] <= cheapest * 100
    assert all(
        o["over_budget_for"] == ["Asha"]
        for o in view["options"]
        if o["per_person"]["amount_minor"] > cheapest * 100
    )


def test_invites_and_membership_rules(client: TestClient, shared: dict[str, Any]) -> None:
    assert client.post(f"{API}/groups/join", json={"invite_code": "nope-nope"}).status_code == 404
    assert client.delete(f"{API}/groups/{shared['id']}/me").status_code == 409  # owner stays
    register(client, "ravi@example.com", "Ravi Mehta")
    client.post(f"{API}/groups/join", json={"invite_code": shared["invite_code"]})
    assert len(client.get(f"{API}/groups").json()["items"]) == 1
    assert client.delete(f"{API}/groups/{shared['id']}/me").status_code == 204
    assert client.get(f"{API}/groups").json()["items"] == []
