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
