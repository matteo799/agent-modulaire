"""Composition root.

This is the ONLY module allowed to import concrete adapters. Everything else
depends on the Protocols in `rag.interfaces`. If you ever need to add a new
backend (e.g., Weaviate), implement the Protocol and add a branch here.

Keeping this in one file makes wiring auditable in one glance — handy for
security review and for catching accidental coupling.

Implementation note on `cast()`:
    Adapter modules (qdrant_store, ollama_client, …) live in untyped 3rd-party
    territory for mypy (heavy ML deps, no stubs). With `ignore_missing_imports`
    on, their classes appear as `Any`, which makes mypy complain about
    "returning Any from a typed function" under --strict.
    `cast(VectorStore, x)` tells mypy "I assert this matches the Protocol";
    correctness is enforced at import / runtime via `runtime_checkable` on
    each Protocol. This is the standard pattern for Protocol-typed factories.
"""

from __future__ import annotations

from typing import cast

from rag.config.settings import Settings
from rag.interfaces import (
    ChildChunk,
    DocumentStore,
    Embedder,
    LLMClient,
    Reranker,
    Retriever,
    VectorStore,
)


def build_vector_store(settings: Settings) -> VectorStore:
    provider = settings.vector_store.provider
    if provider == "qdrant":
        from rag.adapters.vector_stores.qdrant_store import QdrantVectorStore

        qs = settings.vector_store.qdrant
        # Si l'URL est vide, on utilise le mode local embarqué (path sur disque).
        # Si elle est renseignée, on se connecte au serveur Qdrant distant.
        use_local = not qs.url or qs.url.strip() == ""
        return cast(
            VectorStore,
            QdrantVectorStore(
                collection=settings.vector_store.collection,
                url="" if use_local else qs.url,
                api_key=qs.api_key,
                path=settings.data_dir / "qdrant" if use_local else None,
            ),
        )
    raise ValueError(f"Unknown vector_store provider: {provider}")


def build_embedder(settings: Settings) -> Embedder:
    if settings.embedder.provider == "sentence_transformers":
        from rag.adapters.embedders.sentence_transformers_embedder import (
            SentenceTransformersEmbedder,
        )

        return cast(
            Embedder,
            SentenceTransformersEmbedder(
                model=settings.embedder.model,
                device=settings.embedder.device,
                batch_size=settings.embedder.batch_size,
            ),
        )
    raise ValueError(f"Unknown embedder provider: {settings.embedder.provider}")


def build_llm(settings: Settings) -> LLMClient:
    provider = settings.llm.provider
    if provider == "ollama":
        from rag.adapters.llms.ollama_client import OllamaClient

        return cast(
            LLMClient,
            OllamaClient(
                base_url=settings.llm.ollama.base_url,
                model=settings.llm.ollama.model,
                temperature=settings.llm.temperature,
                max_tokens=settings.llm.max_tokens,
                timeout_s=settings.llm.ollama.timeout_s,
            ),
        )
    if provider == "vllm":
        from rag.adapters.llms.vllm_client import VLLMClient

        return cast(
            LLMClient,
            VLLMClient(
                base_url=settings.llm.vllm.base_url,
                model=settings.llm.vllm.model,
                api_key=settings.llm.vllm.api_key,
                temperature=settings.llm.temperature,
                max_tokens=settings.llm.max_tokens,
            ),
        )
    if provider == "openai":
        from rag.adapters.llms.openai_client import OpenAIClient

        return cast(
            LLMClient,
            OpenAIClient(
                base_url=settings.llm.openai.base_url,
                model=settings.llm.openai.model,
                api_key=settings.llm.openai.api_key,
                temperature=settings.llm.temperature,
                max_tokens=settings.llm.max_tokens,
                timeout_s=settings.llm.openai.timeout_s,
            ),
        )
    if provider == "lmstudio":
        from rag.adapters.llms.lmstudio_client import LMStudioClient

        return cast(
            LLMClient,
            LMStudioClient(
                base_url=settings.llm.lmstudio.base_url,
                model=settings.llm.lmstudio.model,
                temperature=settings.llm.temperature,
                max_tokens=settings.llm.max_tokens,
                timeout_s=settings.llm.lmstudio.timeout_s,
            ),
        )
    raise ValueError(f"Unknown llm provider: {provider}")


def build_reranker(settings: Settings) -> Reranker | None:
    if not settings.reranker.enabled:
        return None
    from rag.adapters.rerankers.bge_reranker import BGEReranker

    return cast(
        Reranker,
        BGEReranker(
            model=settings.reranker.model,
            device=settings.reranker.device,
            batch_size=settings.reranker.batch_size,
            max_length=settings.reranker.max_length,
        ),
    )


def build_doc_store(settings: Settings) -> DocumentStore:
    """Construit le DocumentStore (parents). SQLite POC ; Postgres viendra plus tard."""
    from rag.adapters.doc_stores.sqlite_store import SQLiteDocumentStore

    return cast(
        DocumentStore,
        SQLiteDocumentStore(db_path=settings.data_dir / "parents.sqlite"),
    )


def build_retriever(
    settings: Settings,
    *,
    bm25_corpus: list[ChildChunk] | None = None,
) -> Retriever:
    """Assemble la stack retrieval complète.

    Empilement par défaut (sans BM25) :
        Dense → ParentChild → (Reranking si activé)

    Avec BM25 (si on passe le corpus children, p. ex. depuis l'ingestion) :
        Hybrid(Dense, BM25) → ParentChild → (Reranking si activé)

    Pourquoi BM25 n'est pas câblé par défaut : son index est in-memory et a
    besoin du corpus de children, qui n'est pas exposé par le `VectorStore`
    Protocol (et qu'on n'a pas envie de fuiter dans l'interface uniquement
    pour ce cas). Le caller (CLI d'ingestion, eval, …) le passe explicitement.
    """
    from rag.retrieval.dense import DenseRetriever
    from rag.retrieval.parent_child import ParentChildRetriever
    from rag.retrieval.reranking import RerankingRetriever

    embedder = build_embedder(settings)
    vector_store = build_vector_store(settings)
    dense = cast(Retriever, DenseRetriever(embedder=embedder, vector_store=vector_store))

    base: Retriever
    if settings.retrieval.hybrid_enabled:
        if bm25_corpus is None:
            raise ValueError(
                "retrieval.hybrid_enabled=true nécessite que bm25_corpus soit fourni. "
                "Charge la liste des ChildChunks et passe-la à build_retriever()."
            )
        from rag.retrieval.bm25 import BM25Retriever
        from rag.retrieval.hybrid import HybridRetriever

        bm25 = cast(Retriever, BM25Retriever(bm25_corpus))
        base = cast(
            Retriever,
            HybridRetriever(
                sources=[
                    (dense, settings.retrieval.dense_k),
                    (bm25, settings.retrieval.bm25_k),
                ],
                rrf_constant=settings.retrieval.hybrid_rrf_constant,
            ),
        )
    else:
        base = dense

    doc_store = build_doc_store(settings)
    pc: Retriever = cast(Retriever, ParentChildRetriever(inner=base, doc_store=doc_store))

    reranker = build_reranker(settings)
    if reranker is None:
        return pc

    return cast(
        Retriever,
        RerankingRetriever(inner=pc, reranker=reranker, candidate_k=settings.retrieval.dense_k),
    )


def build_crag_graph_from_settings(
    settings: Settings,
    *,
    bm25_corpus: list[ChildChunk] | None = None,
) -> object:
    """Composition root du graphe RAG (M4).

    Dispatche selon `settings.crag.enabled` :
    - True  → graphe CRAG complet (retrieve → grade → decide → rewrite / generate)
    - False → graphe RAG simple   (retrieve → prepare_context → generate)

    Renvoie le graphe LangGraph compilé. Le type est `object` car LangGraph
    n'a pas de stub mypy et qu'on ne veut pas dépendre du module hors factory.
    """
    from rag.graph.builder import build_crag_graph, build_simple_rag_graph

    retriever = build_retriever(settings, bm25_corpus=bm25_corpus)
    llm = build_llm(settings)

    if not settings.crag.enabled:
        return build_simple_rag_graph(
            retriever=retriever,
            llm=llm,
            retrieve_k=settings.retrieval.dense_k,
        )

    return build_crag_graph(
        retriever=retriever,
        llm=llm,
        retrieve_k=settings.retrieval.dense_k,
    )
