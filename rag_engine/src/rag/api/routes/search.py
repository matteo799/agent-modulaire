"""Router `/search` — retrieval pur, debug-only (M3.6).

Renvoie les hits (parents hydratés) + scores. Pas de LLM. Le « vrai »
endpoint utilisateur est `/query` (M5.2).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from rag.api.deps import get_retriever
from rag.interfaces import Retriever, SearchHit

router = APIRouter(tags=["debug"])


class SearchResponse(BaseModel):
    query: str
    k: int
    hits: list[SearchHit]


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1, description="La question utilisateur"),
    k: int = Query(5, ge=1, le=50, description="Nombre de hits à renvoyer"),
    retriever: Retriever = Depends(get_retriever),
) -> SearchResponse:
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query cannot be empty")
    hits = retriever.retrieve(query=query, k=k)
    return SearchResponse(query=query, k=k, hits=hits)
