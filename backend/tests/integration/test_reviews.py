"""Hotel reviews: imported reviews with the average rating, and verified-stay reviews."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import BookingItem
from tests.integration.test_bookings import (
    API,
    GOOD_CARD,
    code,
    flight_offer,
    hold,
    hotel_room,
    pay,
    signed_in,  # noqa: F401  (fixture)
)

REVIEW = {
    "rating": 9,
    "title": "Lovely stay",
    "text": "The staff were friendly and the room was spotless. Great location too.",
    "traveller_type": "couple",
}


def booked_stay(client: TestClient) -> dict[str, Any]:
    created = hold(client, [hotel_room(client)])
    paid = pay(client, created.json()["id"], GOOD_CARD)
    assert paid.status_code == 200, paid.text
    return dict(paid.json())


def check_out(db: Session, booking: dict[str, Any]) -> None:
    """Move the stay into the past (the API clock cannot jump days: tokens would expire)."""
    item = db.get(BookingItem, uuid.UUID(booking["items"][0]["id"]))
    assert item is not None
    item.starts_at -= timedelta(days=10)
    item.ends_at -= timedelta(days=10)
    db.commit()


def review_url(booking: dict[str, Any]) -> str:
    return f"{API}/bookings/{booking['id']}/items/{booking['items'][0]['id']}/review"


def test_supplied_reviews_are_summarised(signed_in: TestClient) -> None:  # noqa: F811
    client = signed_in
    hotel_id = client.get(
        f"{API}/hotels/search",
        params={
            "city": client.get(f"{API}/locations", params={"q": "Mumbai", "kind": "city"}).json()[
                "items"
            ][0]["value"],
            "check_in": "2026-11-14",
            "check_out": "2026-11-16",
        },
    ).json()["results"][0]["id"]
    body = client.get(f"{API}/hotels/{hotel_id}/reviews", params={"limit": 50}).json()
    summary = body["summary"]
    assert summary["total"] >= 3 and len(body["items"]) == summary["total"]
    assert "generated text" in summary["note"]
    assert 0 < summary["average_rating"] <= 10
    assert all(i["source"] == "supplied" and not i["verified_stay"] for i in body["items"])
    dates = [i["date"] for i in body["items"]]
    assert dates == sorted(dates, reverse=True)
    highest = client.get(f"{API}/hotels/{hotel_id}/reviews", params={"sort": "highest"}).json()
    ratings = [i["rating"] for i in highest["items"]]
    assert ratings == sorted(ratings, reverse=True)
    assert client.get(f"{API}/hotels/{uuid.uuid4()}/reviews").status_code == 404


def test_traveller_reviews_a_completed_stay(
    signed_in: TestClient,  # noqa: F811
    db_session: Session,
) -> None:
    client = signed_in
    booking = booked_stay(client)
    early = client.post(review_url(booking), json=REVIEW)
    assert early.status_code == 409 and code(early) == "REVIEW_TOO_EARLY"
    assert client.get(f"{API}/me/reviews").json()["awaiting"] == []

    check_out(db_session, booking)
    awaiting = client.get(f"{API}/me/reviews").json()["awaiting"]
    assert [a["item_id"] for a in awaiting] == [booking["items"][0]["id"]]
    spam = client.post(review_url(booking), json={**REVIEW, "text": REVIEW["text"] + " www.x.io"})
    assert spam.status_code == 422 and code(spam) == "REVIEW_CONTENT"

    written = client.post(review_url(booking), json=REVIEW)
    assert written.status_code == 201, written.text
    review = written.json()
    assert review["verified_stay"] and review["rating"] == REVIEW["rating"]
    again = client.post(review_url(booking), json=REVIEW)
    assert again.status_code == 409 and code(again) == "REVIEW_EXISTS"

    mine = client.get(f"{API}/me/reviews").json()
    assert [r["id"] for r in mine["written"]] == [review["id"]] and mine["awaiting"] == []
    listed = client.get(f"{API}/hotels/{review['hotel_id']}/reviews", params={"limit": 50}).json()[
        "items"
    ]
    assert any(i["id"] == review["id"] and i["source"] == "traveller" for i in listed)

    assert client.delete(f"{API}/me/reviews/{review['id']}").status_code == 204
    assert client.get(f"{API}/me/reviews").json()["written"] == []
    assert client.delete(f"{API}/me/reviews/{review['id']}").status_code == 404


def test_only_stays_can_be_reviewed(signed_in: TestClient) -> None:  # noqa: F811
    client = signed_in
    created = hold(client, [{"kind": "flight", "offer_id": flight_offer(client), "adults": 1}])
    booking = pay(client, created.json()["id"], GOOD_CARD).json()
    response = client.post(review_url(booking), json=REVIEW)
    assert response.status_code == 422 and code(response) == "NOT_A_STAY"
    short = client.post(review_url(booking), json={**REVIEW, "text": "too short"})
    assert short.status_code == 422
