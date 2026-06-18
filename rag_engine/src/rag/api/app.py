"""FastAPI app — composition root des routers + middleware (M5).

Toute la logique métier vit dans les routers (`rag.api.routes.*`). Ce module
ne fait que les assembler et brancher le middleware `query_id`. Les
dépendances injectables sont dans `rag.api.deps`.

Re-exports : `get_retriever` reste accessible depuis `rag.api.app` pour la
rétro-compat avec les tests M3.6 qui le surchargent.
"""

from __future__ import annotations

from fastapi import FastAPI

from rag.api.deps import (  # noqa: F401 — re-exports publics
    get_graph,
    get_retriever,
    get_settings,
)
from rag.api.middleware import QueryIdMiddleware
from rag.api.routes.health import router as health_router
from rag.api.routes.ingest import router as ingest_router
from rag.api.routes.query import router as query_router
from rag.api.routes.search import router as search_router


def create_app() -> FastAPI:
    """Factory de l'app. Permet aux tests de créer des instances isolées
    (utile si on veut éviter le partage de `dependency_overrides` entre tests).
    """
    app = FastAPI(
        title="rag-engine",
        description="Parent-Child + Corrective RAG (POC)",
        version="0.1.0",
    )
    app.add_middleware(QueryIdMiddleware)
    app.include_router(health_router)
    app.include_router(search_router)
    app.include_router(ingest_router)
    app.include_router(query_router)
    return app


# Instance par défaut consommée par `uvicorn rag.api.app:app`.
app = create_app()
