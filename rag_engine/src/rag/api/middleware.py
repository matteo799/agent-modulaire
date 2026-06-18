"""Middleware FastAPI : `query_id` + access logs (M5.5).

Pour chaque requête entrante on :
1. Lit `X-Query-Id` du header si présent (utile pour corréler côté client),
   sinon on en génère un frais via `rag.utils.context.new_query_id`.
2. Bind ce `query_id` dans le contexte `structlog.contextvars` → toutes
   les lignes de log émises pendant le traitement de la requête le portent
   automatiquement, sans qu'on doive le passer en argument.
3. Log un access record en sortie (méthode, path, status, durée ms).
4. Renvoie le `query_id` dans le header `X-Query-Id` de la réponse pour
   permettre au client de l'inclure dans un ticket de support.

Endpoints exclus : `/healthz` (et `/readyz`), pour ne pas polluer les logs
avec le bruit des probes kubernetes (un check / 10s, 24h/24).
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from rag.utils.context import new_query_id, query_id_context
from rag.utils.logging import get_logger

_log = get_logger(__name__)

_HEADER = "X-Query-Id"
_QUIET_PATHS = frozenset({"/healthz", "/readyz"})


class QueryIdMiddleware(BaseHTTPMiddleware):
    """Génère / propage un query_id et log l'accès."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Priorité au header client : utile pour les retries idempotents
        # côté caller (mêmes requêtes = même query_id côté logs).
        qid = request.headers.get(_HEADER) or new_query_id()
        path = request.url.path
        quiet = path in _QUIET_PATHS

        start = time.perf_counter()
        with query_id_context(qid):
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start) * 1000.0
            if not quiet:
                _log.info(
                    "http.access",
                    method=request.method,
                    path=path,
                    status=response.status_code,
                    duration_ms=round(duration_ms, 2),
                )
            response.headers[_HEADER] = qid
        return response
