"""Dépendances FastAPI partagées.

Centralise les providers `Depends(...)` pour qu'ils soient :
- importables depuis n'importe quel router sans cycle,
- override-ables en test via `app.dependency_overrides[provider]`.

`lru_cache(maxsize=1)` est utilisé sur les builders coûteux (settings,
retriever, graphe) pour les traiter en singleton par process. Si tu changes
une variable d'env en cours d'exécution, redémarre l'app.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from rag.config.factory import (
    build_crag_graph_from_settings,
    build_retriever,
)
from rag.config.settings import Settings, load_settings
from rag.interfaces import Retriever
from rag.observability import build_langfuse_handler

# --- settings -------------------------------------------------------------


@lru_cache(maxsize=1)
def _cached_settings() -> Settings:
    return load_settings()


def get_settings() -> Settings:
    """Override-able en test via `app.dependency_overrides[get_settings]`."""
    return _cached_settings()


# --- retriever (utilisé par /search) --------------------------------------


@lru_cache(maxsize=1)
def _cached_retriever() -> Retriever:
    return build_retriever(_cached_settings())


def get_retriever() -> Retriever:
    return _cached_retriever()


# --- graphe CRAG (utilisé par /query et /query/stream) --------------------


@lru_cache(maxsize=1)
def _cached_graph() -> Any:
    return build_crag_graph_from_settings(_cached_settings())


def get_graph() -> Any:
    """Renvoie le graphe LangGraph compilé. Type `Any` car LangGraph n'a pas de stub."""
    return _cached_graph()


# --- callbacks LangChain (Langfuse — M6.6) -------------------------------


@lru_cache(maxsize=1)
def _cached_langfuse_handler() -> Any | None:
    return build_langfuse_handler(_cached_settings())


def get_langfuse_handler() -> Any | None:
    """Handler Langfuse si activé en config, sinon None. Override-able en test."""
    return _cached_langfuse_handler()
