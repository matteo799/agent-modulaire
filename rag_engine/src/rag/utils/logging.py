"""Structured logging configuration.

`structlog` is the only logger we use. Rationale:
- every log line must be a JSON object with a stable shape (Loki / ELK in prod),
- yet remain readable in a dev terminal.

Two output modes, selected at startup:
- console (dev): colored, human-friendly
- json (prod):   single-line JSON ready for ingestion

The current `query_id` (and any other field bound via `structlog.contextvars`)
is attached automatically to every record by the `merge_contextvars` processor.
See `rag.utils.context` for the public API.

Usage:
    from rag.utils.logging import configure_logging, get_logger

    configure_logging(level="INFO", json_output=False)  # once, at startup
    log = get_logger(__name__)
    log.info("ingested", source="cours.pdf", chunks=42)
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.typing import Processor


def configure_logging(
    level: str = "INFO",
    *,
    json_output: bool = False,
) -> None:
    """Configure structlog process-wide. Idempotent — safe to call multiple times.

    Args:
        level: minimum level, case-insensitive (DEBUG/INFO/WARNING/ERROR/CRITICAL).
        json_output: True for production (JSON), False for development (console).
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Order matters: contextvars first so values bound via
    # `structlog.contextvars.bind_contextvars` (including our query_id helpers)
    # land in every record, then enrichment, then rendering at the very end.
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: Processor = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> Any:
    """Convenience wrapper. Use this instead of `logging.getLogger`.

    Returns `Any` rather than the precise structlog type because the latter
    is parameterised on the wrapper class and adds noise to every call site
    without a real type-safety win — `mypy --strict` is happier this way.
    """
    return structlog.get_logger(name)
