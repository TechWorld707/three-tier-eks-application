import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from time import perf_counter

from flask import Response, g, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)
from sqlalchemy import event
from sqlalchemy.exc import TimeoutError

REQUESTS = Counter(
    "three_tier_http_requests_total", "Completed HTTP requests", ("route", "method", "status")
)
DURATION = Histogram(
    "three_tier_http_request_duration_seconds", "HTTP request duration", ("route", "method")
)
POOL_IN_USE = Gauge(
    "three_tier_db_pool_connections_in_use",
    "Database connections checked out by live workers",
    multiprocess_mode="livesum",
)
POOL_TIMEOUTS = Counter(
    "three_tier_db_pool_checkout_timeouts_total", "Database pool checkout timeouts"
)


class JsonFormatter(logging.Formatter):
    def format(self, record):
        from opentelemetry import trace

        data = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        request_id = getattr(g, "request_id", None) if request else None
        if request_id:
            data["request_id"] = request_id

        context = trace.get_current_span().get_span_context()
        if context.is_valid:
            data["trace_id"] = format(context.trace_id, "032x")
            data["span_id"] = format(context.span_id, "016x")
        if hasattr(record, "http"):
            data.update(record.http)
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data)


def configure_observability(app, engine):
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    app.logger.handlers[:] = [handler]
    app.logger.setLevel(logging.INFO)
    app.logger.propagate = False

    if os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"):
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource.create({
            "service.name": os.getenv("OTEL_SERVICE_NAME", "three-tier-backend"),
        }))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        FlaskInstrumentor().instrument_app(app, tracer_provider=provider)
        SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=provider)

    @event.listens_for(engine, "checkout")
    def on_checkout(dbapi_connection, connection_record, connection_proxy):
        POOL_IN_USE.inc()

    @event.listens_for(engine, "checkin")
    def on_checkin(dbapi_connection, connection_record):
        POOL_IN_USE.dec()

    @app.before_request
    def start_request():
        request_id = request.headers.get("X-Request-ID", "")
        g.request_id = request_id if re.fullmatch(r"[0-9a-f]{32}", request_id) else uuid.uuid4().hex
        g.started_at = perf_counter()

    @app.after_request
    def record_request(response):
        response.headers["X-Request-ID"] = g.request_id
        if request.path in {"/health", "/metrics"}:
            return response

        route = request.url_rule.rule if request.url_rule else "unmatched"
        method = request.method if request.method in {"GET", "POST", "HEAD", "OPTIONS"} else "OTHER"
        duration = perf_counter() - g.started_at
        REQUESTS.labels(route, method, str(response.status_code)).inc()
        DURATION.labels(route, method).observe(duration)
        app.logger.info("HTTP request", extra={"http": {
            "route": route,
            "method": method,
            "status": response.status_code,
            "duration_seconds": round(duration, 6),
        }})
        return response

    @app.get("/metrics")
    def metrics():
        registry = REGISTRY
        if os.getenv("PROMETHEUS_MULTIPROC_DIR"):
            registry = CollectorRegistry()
            multiprocess.MultiProcessCollector(registry)
        return Response(generate_latest(registry), content_type=CONTENT_TYPE_LATEST)


def record_database_error(error):
    if isinstance(error, TimeoutError):
        POOL_TIMEOUTS.inc()
