"""Request-scoped context, primarily for propagating `query_id` across layers.

The motivation: when a query enters the API, we assign it a unique id. We want
that id to appear in every log line emitted during the processing of that
query, without manually threading it through every function signature.

Under the hood we use `structlog.contextvars`:
- it is async-safe (PEP 567 contextvars, correctly scoped to a task),
- it is thread-safe,
- `structlog.contextvars.merge_contextvars` is already in our logging pipeline,
  which means bound values land in every log record automatically (and also
  in `structlog.testing.capture_logs`, which uses the same merge step).

The public API stays minimal so callers don't need to know about structlog:
    new_query_id()         -> str               # generate a fresh UUID4
    get_query_id()         -> str | None        # read current value
    set_query_id(qid)      -> None              # one-shot bind (middleware-style)
    query_id_context(qid)  -> ContextManager    # scoped bind + auto-restore
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import structlog

# Bound key used in structlog's contextvars dict. Kept as a constant so we
# only have a single place to change if we ever rename it.
_QUERY_ID_KEY = "query_id"


def new_query_id() -> str:
    """Return a fresh, unique query id (UUID4 string form)."""
    return str(uuid.uuid4())


def get_query_id() -> str | None:
    """Return the current query id, or None if no query context is active."""
    value = structlog.contextvars.get_contextvars().get(_QUERY_ID_KEY)
    return value if isinstance(value, str) else None


def set_query_id(query_id: str) -> None:
    """Bind a query id to the current context, with no auto-restore.

    Intended for code paths where lifetime is managed externally (e.g., a
    FastAPI middleware that sets it on request entry and the request scope
    is torn down at the end). For tests / scripts, prefer `query_id_context`.
    """
    structlog.contextvars.bind_contextvars(**{_QUERY_ID_KEY: query_id})


@contextmanager
def query_id_context(query_id: str | None = None) -> Iterator[str]:
    """Scoped binder: enters with `query_id`, restores the previous value on exit.

    If no id is provided, a fresh UUID4 is generated and returned.

    Nesting is supported: on exit we restore the outer value if there was one,
    or clear the key if not. This mirrors the behaviour you'd expect from a
    classic ContextVar token-based reset.

    Example:
        with query_id_context() as qid:
            log.info("processing")  # log line includes query_id=<qid>
    """
    qid = query_id or new_query_id()
    previous = structlog.contextvars.get_contextvars().get(_QUERY_ID_KEY)
    structlog.contextvars.bind_contextvars(**{_QUERY_ID_KEY: qid})
    try:
        yield qid
    finally:
        if previous is None:
            structlog.contextvars.unbind_contextvars(_QUERY_ID_KEY)
        else:
            structlog.contextvars.bind_contextvars(**{_QUERY_ID_KEY: previous})
