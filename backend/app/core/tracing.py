"""Optional distributed tracing (OpenTelemetry).

Off unless OTEL_EXPORTER_OTLP_ENDPOINT is set, so the app never depends on a tracing backend.
With the `obs` Compose profile, traces go to Jaeger: one request shows the FastAPI span and every
SQL statement under it, e.g. a search -> pricing -> database round trip.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sqlalchemy import Engine, event

from app import __version__
from app.core.config import Settings

_configured = False


def configure_tracing(
    app: FastAPI, settings: Settings, engine_factory: Callable[[], Engine]
) -> bool:
    global _configured
    if not settings.otel_exporter_otlp_endpoint:
        return False
    if not _configured:
        provider = TracerProvider(
            resource=Resource.create(
                {
                    "service.name": settings.otel_service_name,
                    "service.version": __version__,
                    "deployment.environment": settings.environment,
                }
            )
        )
        endpoint = settings.otel_exporter_otlp_endpoint.rstrip("/") + "/v1/traces"
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
        _trace_sql(engine_factory())
        _configured = True
    FastAPIInstrumentor.instrument_app(app, excluded_urls="metrics,api/v1/health,api/v1/ready")
    return True


def _trace_sql(engine: Engine) -> None:
    """One span per SQL statement under the current request span.

    Written with SQLAlchemy's own cursor events (rather than the contrib instrumentor, which does
    not support SQLAlchemy 2.1). Only the statement text is recorded, never parameter values, so
    traveller data cannot leak into traces.
    """
    tracer = trace.get_tracer("tripmind.db")

    @event.listens_for(engine, "before_cursor_execute")
    def _start(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        verb = statement.lstrip().split(" ", 1)[0].upper()
        span = tracer.start_span(
            f"db {verb}",
            attributes={
                "db.system": engine.dialect.name,
                "db.statement": statement[:500],
                "db.executemany": bool(executemany),
            },
        )
        conn.info.setdefault("tripmind_spans", []).append(span)

    @event.listens_for(engine, "after_cursor_execute")
    def _end(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        spans = conn.info.get("tripmind_spans")
        if spans:
            spans.pop().end()

    @event.listens_for(engine, "handle_error")
    def _error(context):  # type: ignore[no-untyped-def]
        spans = context.connection.info.get("tripmind_spans") if context.connection else None
        if spans:
            span = spans.pop()
            span.record_exception(context.original_exception)
            span.end()
