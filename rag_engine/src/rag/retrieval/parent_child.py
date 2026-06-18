"""ParentChildRetriever — dédoublonne par parent et hydrate avec le contexte parent.

Pattern Parent-Child : on indexe des chunks fins (children) pour la précision
du retrieval, mais on injecte des chunks larges (parents) dans le prompt du
LLM pour qu'il ait assez de contexte. Cet objet fait le pont :

1. Délègue le retrieval à un retriever interne (dense / BM25 / hybride).
2. Lit le `parent_id` dans les metadata de chaque hit (le pipeline d'ingestion
   l'y a déposé via `_to_vector_item` ; BM25Retriever fait pareil).
3. Dédoublonne : si deux children pointent vers le même parent, un seul hit
   sort, avec le score MAX des children (« le parent est aussi pertinent
   que son meilleur child »).
4. Hydrate les parents depuis le `DocumentStore` et retourne des `SearchHit`
   pointant désormais sur les parents (id = parent_id, text = parent.text).

Choix `child_k_multiplier` : pour récupérer `k` parents uniques en sortie, il
faut interroger l'inner retriever avec plus de `k` children, car plusieurs
children peuvent partager un parent. Multiplicateur 3 par défaut — empirique,
ajustable via config plus tard si l'éval M6 le justifie.

Implémente `Retriever`. Composable : on peut empiler `Reranking → ParentChild
→ Hybrid` ou `ParentChild → Hybrid` selon la stratégie.
"""

from __future__ import annotations

from typing import Any

from rag.interfaces import DocumentStore, Retriever, SearchHit
from rag.utils.logging import get_logger

_log = get_logger(__name__)


class ParentChildRetriever:
    """Wrap un retriever de children → dédoublonne par parent → hydrate parents."""

    def __init__(
        self,
        inner: Retriever,
        doc_store: DocumentStore,
        *,
        child_k_multiplier: int = 3,
    ) -> None:
        if child_k_multiplier < 1:
            raise ValueError("child_k_multiplier doit être >= 1")
        self._inner = inner
        self._doc_store = doc_store
        self._mult = child_k_multiplier

    def retrieve(
        self,
        query: str,
        k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        if k <= 0:
            return []

        # On élargit la fenêtre côté children pour absorber le dédoublonnage.
        inner_k = k * self._mult
        child_hits = self._inner.retrieve(query=query, k=inner_k, filters=filters)
        if not child_hits:
            return []

        # Dédup par parent_id, en gardant le meilleur score child + l'ordre
        # de première apparition (stable wrt l'ordre du retriever interne).
        best_by_parent: dict[str, float] = {}
        order: list[str] = []
        skipped = 0
        for hit in child_hits:
            parent_id = hit.metadata.get("parent_id")
            if not isinstance(parent_id, str) or not parent_id:
                # Un child sans parent_id est un bug d'ingestion ; on le saute
                # plutôt que de planter le pipeline en interrogation.
                skipped += 1
                continue
            if parent_id not in best_by_parent:
                best_by_parent[parent_id] = hit.score
                order.append(parent_id)
            else:
                best_by_parent[parent_id] = max(best_by_parent[parent_id], hit.score)

        if skipped:
            _log.warning("parent_child: child hits without parent_id", skipped=skipped)

        if not order:
            return []

        # Tri stable par score décroissant ; en cas d'égalité, l'ordre d'origine
        # (donc l'ordre du retriever interne) est préservé grâce à `sorted`.
        ranked_parents = sorted(order, key=lambda pid: best_by_parent[pid], reverse=True)
        top_parents = ranked_parents[:k]

        # Hydratation : on charge les parents en un seul appel au DocumentStore.
        parents = self._doc_store.get(top_parents)
        by_id = {p.id: p for p in parents}

        out: list[SearchHit] = []
        missing = 0
        for pid in top_parents:
            parent = by_id.get(pid)
            if parent is None:
                # Un parent_id présent dans le vector store mais absent du
                # doc store : incohérence d'ingestion. On log et on saute.
                missing += 1
                continue
            out.append(
                SearchHit(
                    id=parent.id,
                    text=parent.text,
                    score=best_by_parent[pid],
                    metadata=parent.metadata.model_dump(mode="json"),
                )
            )

        if missing:
            _log.warning("parent_child: parents missing from doc store", missing=missing)

        return out
