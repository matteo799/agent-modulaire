"""Router `/query` (M5.2) + `/query/stream` (M5.3) — endpoint utilisateur principal.

`/query`        : synchrone, renvoie l'`Answer` complète une fois le graphe terminé.
`/query/stream` : SSE (Server-Sent Events) — émet un event par phase du graphe
                  pour que le client puisse afficher la progression, et un
                  event final avec l'`Answer` JSON.

Pourquoi SSE et pas WebSocket : SSE est unidirectionnel serveur→client,
exactement ce qu'on veut, et marche derrière n'importe quel proxy HTTP.
Pas de handshake spécial, pas de lib en plus côté client (EventSource est
natif navigateur). `StreamingResponse` de Starlette suffit.

Pour le POC, on ne stream PAS token-par-token : LangGraph streame des
updates d'état entre nœuds, pas des deltas de génération. On stream donc :
1. `start`     — la query qu'on traite,
2. `node:<n>`  — à chaque sortie de nœud, on indique où on en est,
3. `answer`    — la réponse finale,
4. `done`      — fermeture explicite.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from rag.api.deps import get_graph, get_langfuse_handler
from rag.interfaces.types import Answer, CRAGState

router = APIRouter(tags=["query"])


class QueryRequest(BaseModel):
    """Corps JSON du POST /query.

    `max_iterations` est exposé pour permettre des tests rapides (un seul tour)
    et des cas exigeants (plus de retries). Défaut conservateur côté serveur.
    """

    question: str = Field(..., min_length=1, max_length=2000)
    max_iterations: int = Field(default=2, ge=0, le=5)


class QueryResponse(BaseModel):
    """Réponse JSON du POST /query."""

    question: str
    answer: Answer
    fallback_triggered: bool


def _initial_state(req: QueryRequest) -> CRAGState:
    q = req.question.strip()
    if not q:
        raise HTTPException(status_code=400, detail="question cannot be empty")
    return CRAGState(
        original_query=q,
        query=q,
        max_iterations=req.max_iterations,
    )


def _extract_field(final: Any, name: str) -> Any:
    """Récupère un champ depuis l'état final, dict OU pydantic.

    LangGraph renvoie un dict en mode strict-types, l'objet pydantic en
    mode permissif. On supporte les deux.
    """
    if isinstance(final, dict):
        return final.get(name)
    return getattr(final, name, None)


def _runnable_config(handler: Any | None) -> dict[str, Any] | None:
    """Construit la config LangChain runnable à passer à invoke/stream.

    Retourne None si pas de handler — évite de polluer l'appel avec un
    dict vide quand le tracing est désactivé.
    """
    if handler is None:
        return None
    return {"callbacks": [handler]}


@router.post("/query", response_model=QueryResponse)
def query_endpoint(
    req: QueryRequest,
    graph: Any = Depends(get_graph),
    langfuse: Any = Depends(get_langfuse_handler),
) -> QueryResponse:
    initial = _initial_state(req)
    config = _runnable_config(langfuse)
    final = graph.invoke(initial, config=config) if config else graph.invoke(initial)

    answer = _extract_field(final, "answer")
    if answer is None:
        # Sécurité : si le graphe termine sans answer (bug), on renvoie 500.
        raise HTTPException(status_code=500, detail="graph terminated without answer")

    return QueryResponse(
        question=req.question.strip(),
        answer=answer,
        fallback_triggered=bool(_extract_field(final, "fallback_triggered")),
    )


# --- M5.3 : streaming SSE -------------------------------------------------


def _sse_event(event: str, data: dict[str, Any]) -> bytes:
    """Encode un event SSE selon la spec :

        event: <type>
        data: <json>
        \n

    Toutes les implémentations clientes (EventSource navigateur, httpx, ...)
    réassemblent ce format.
    """
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n".encode()


def _stream_from_graph(
    graph: Any,
    initial: CRAGState,
    *,
    config: dict[str, Any] | None = None,
) -> Iterable[bytes]:
    """Lance le graphe en mode stream et yield des events SSE.

    LangGraph compilé expose `.stream(state, config=...)` qui yield un dict
    par étape : `{"<node_name>": <node_output_dict>}`. On répercute en event SSE.
    Si le graphe ne supporte pas `.stream` (vieille version, mock), on
    retombe sur `.invoke()` et on yield juste l'answer finale.

    `config` est la config LangChain runnable (avec callbacks Langfuse).
    """
    yield _sse_event(
        "start", {"question": initial.original_query, "max_iterations": initial.max_iterations}
    )

    stream_fn = getattr(graph, "stream", None)
    if callable(stream_fn):
        # Mode streaming natif LangGraph.
        last_state: dict[str, Any] = {}
        stream_iter = stream_fn(initial, config=config) if config else stream_fn(initial)
        for update in stream_iter:
            # `update` : {"<node>": {<delta>}}
            if not isinstance(update, dict):
                continue
            for node_name, delta in update.items():
                last_state.update(delta if isinstance(delta, dict) else {})
                yield _sse_event(
                    "node",
                    {"node": node_name, "keys_updated": list((delta or {}).keys())},
                )
        answer = last_state.get("answer")
        fallback = bool(last_state.get("fallback_triggered", False))
    else:
        # Fallback synchrone.
        final = graph.invoke(initial, config=config) if config else graph.invoke(initial)
        answer = _extract_field(final, "answer")
        fallback = bool(_extract_field(final, "fallback_triggered"))

    if answer is None:
        yield _sse_event("error", {"detail": "graph terminated without answer"})
    else:
        # L'Answer est un BaseModel pydantic → on dump en JSON-friendly dict.
        answer_payload = answer.model_dump(mode="json") if hasattr(answer, "model_dump") else answer
        yield _sse_event(
            "answer",
            {"answer": answer_payload, "fallback_triggered": fallback},
        )

    yield _sse_event("done", {})


@router.post("/query/stream")
def query_stream_endpoint(
    req: QueryRequest,
    graph: Any = Depends(get_graph),
    langfuse: Any = Depends(get_langfuse_handler),
) -> StreamingResponse:
    initial = _initial_state(req)
    config = _runnable_config(langfuse)
    return StreamingResponse(
        _stream_from_graph(graph, initial, config=config),
        media_type="text/event-stream",
        headers={
            # Désactive le buffering côté proxy (nginx) — sinon les events
            # s'accumulent et ne s'écoulent pas en temps réel.
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
