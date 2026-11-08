"""Prometheus metrics.

Labels are deliberately low-cardinality: route templates, never raw paths, user IDs or emails.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "HTTP requests by route template, method and status code.",
    ["method", "route", "status"],
)

HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency by route template and method.",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

AUTH_EVENTS = Counter(
    "auth_events_total",
    "Authentication events by type and outcome.",
    ["event", "outcome"],
)

# ── Business signals (plan v2, section 5). Labels are small fixed sets. ─────────────────────────

SEARCHES = Counter(
    "searches_total",
    "User searches by vertical and whether anything was found.",
    ["vertical", "result"],  # result: found | empty
)

SEARCH_LATENCY = Histogram(
    "search_duration_seconds",
    "Search latency by vertical.",
    ["vertical"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

BOOKING_HOLDS = Counter(
    "booking_holds_total",
    "Checkout hold attempts by outcome.",
    ["outcome"],  # created | sold_out | price_changed | replayed
)

PAYMENTS = Counter("payments_total", "Simulated card payments by outcome.", ["outcome"])

BOOKING_REVENUE = Counter(
    "booking_revenue_minor_total", "Confirmed booking value in minor units.", ["currency"]
)

REFUNDS = Counter("refunds_minor_total", "Refunded value in minor units.", ["currency", "reason"])

HOLDS_EXPIRED = Counter("holds_expired_total", "Unpaid holds that expired and were released.")

BOOKING_CHANGES = Counter(
    "booking_changes_total", "Flight and stay changes by kind and outcome.", ["kind", "outcome"]
)

PLANS = Counter("trip_plans_total", "Connected-trip plans generated, by priority.", ["priority"])

DISRUPTIONS = Counter("disruptions_total", "Recorded disruptions by kind.", ["kind"])

RECOVERY_RESOLUTIONS = Counter(
    "recovery_resolutions_total",
    "Recovery cases resolved by the traveller's choice.",
    ["resolution"],
)

AI_REQUESTS = Counter(
    "ai_requests_total",
    "Hosted LLM calls by provider, feature and outcome.",
    [
        "provider",
        "feature",
        "outcome",
    ],  # ok | cached | rate_limited | server_error | error | invalid_output
)

AI_FALLBACKS = Counter(
    "ai_fallbacks_total", "AI features answered by rules because no provider answered.", ["feature"]
)
