"""Wrapper RAGAS (M6.3) — faithfulness + answer_relevancy.

RAGAS exige un LLM pour grader la fidélité (un LLM-juge externe). En POC
on s'appuie sur la même config LLM que le reste du projet (Ollama par
défaut). Si pas de clé OpenAI / Ollama dispo, le caller peut passer son
propre wrapper langchain via le param `llm`.

Imports paresseux : `ragas`, `datasets` et `langchain_*` sont volumineux
et inutiles tant qu'on ne lance pas l'éval. Importer ce module reste
gratuit pour les tests des autres métriques.

Schéma RAGAS attendu (dataset HuggingFace) :
    {
        "question":     [str],
        "answer":       [str],
        "contexts":     [list[str]],   # contextes injectés au prompt
        "ground_truth": [str],          # réponse idéale du golden
    }
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .golden import GoldenItem
from rag.interfaces.types import Answer


class RagasInputItem(BaseModel):
    """Une ligne du dataset RAGAS, sous notre forme typée."""

    item_id: str
    question: str
    answer: str
    contexts: list[str] = Field(default_factory=list)
    ground_truth: str


class RagasReport(BaseModel):
    """Métriques RAGAS agrégées sur le batch."""

    n_items: int
    faithfulness: float
    answer_relevancy: float
    raw: dict[str, Any] = Field(default_factory=dict)


def build_inputs(
    triples: list[tuple[GoldenItem, Answer, list[str]]],
) -> list[RagasInputItem]:
    """Transforme nos triplets `(golden_item, answer, contexts)` en lignes RAGAS.

    `contexts` est typiquement `state.refined_chunks` après le knowledge
    strip — c'est ce que le LLM a réellement vu dans son prompt `generate`.
    """
    return [
        RagasInputItem(
            item_id=item.id,
            question=item.question,
            answer=answer.text,
            contexts=list(contexts),
            ground_truth=item.expected_answer,
        )
        for item, answer, contexts in triples
    ]


def _to_dataset(inputs: list[RagasInputItem]) -> Any:
    """Construit le `datasets.Dataset` que RAGAS attend.

    Sépaération pour pouvoir mocker l'appel `Dataset.from_dict` dans les
    tests sans charger réellement le module `datasets`.
    """
    from datasets import Dataset  # type: ignore[import-not-found]

    return Dataset.from_dict(
        {
            "question": [x.question for x in inputs],
            "answer": [x.answer for x in inputs],
            "contexts": [x.contexts for x in inputs],
            "ground_truth": [x.ground_truth for x in inputs],
        }
    )


def evaluate_with_ragas(
    inputs: list[RagasInputItem],
    *,
    llm: Any | None = None,
    embeddings: Any | None = None,
) -> RagasReport:
    """Lance RAGAS faithfulness + answer_relevancy.

    Args:
        inputs: lignes pré-construites via `build_inputs`.
        llm: LLM langchain optionnel (sinon RAGAS choisit OpenAI par défaut).
        embeddings: idem côté embeddings.

    Returns:
        Un `RagasReport` agrégé.
    """
    if not inputs:
        return RagasReport(n_items=0, faithfulness=0.0, answer_relevancy=0.0)

    # Imports paresseux pour la même raison que `_to_dataset`.
    from ragas import evaluate  # type: ignore[import-not-found]
    from ragas.metrics import (  # type: ignore[import-not-found]
        answer_relevancy,
        faithfulness,
    )

    dataset = _to_dataset(inputs)
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy],
        llm=llm,
        embeddings=embeddings,
    )
    # `result` est un objet ragas, on accède aux scores via dict-like.
    raw_dict: dict[str, Any] = dict(result) if hasattr(result, "keys") else {}
    return RagasReport(
        n_items=len(inputs),
        faithfulness=float(raw_dict.get("faithfulness", 0.0)),
        answer_relevancy=float(raw_dict.get("answer_relevancy", 0.0)),
        raw=raw_dict,
    )
