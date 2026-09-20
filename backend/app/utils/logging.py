"""
Structured logging configuration.

We use `structlog` so that every log line is a structured, machine-parseable event
(JSON in production) rather than an ad-hoc string. This matters for SafeWalk because
requests fan out into several external calls (Overpass, Nominatim, OSRM, weather,
crime data) and we need to be able to trace a single request across all of them in
log aggregation tools, without leaking internal exception details to API clients
(that's handled separately by the exception handlers in `app/main.py`).
"""

import logging
import sys

import structlog

from app.utils.config import get_settings


def configure_logging() -> None:
    """Configure stdlib logging + structlog. Call once at application startup."""
    settings = get_settings()

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.log_level,
    )

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if settings.log_json
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, settings.log_level)),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Convenience accessor so other modules do `get_logger(__name__)`."""
    return structlog.get_logger(name)
