"""Citation accuracy (M6.4) — métrique custom.

On veut répondre à : « quand le modèle cite [n], la source pointée est-elle
bien dans la liste des sources attendues pour cette question ? »

Trois sous-scores par item, agrégés en moyenne sur le golden :

- **precision** : sur N citations émises, combien pointent vers un
  `expected_source_file` ? (faux positifs = citations bidon)
- **recall**    : sur les sources attendues, combien sont citées au moins
  une fois ? (faux négatifs = sources manquantes)
- **f1**        : harmonique des deux.

Convention pour le cas out-of-domain (`expected_source_files == []`) :
- precision = 1.0 si aucune citation émise (refus correct), 0.0 sinon
  (le modèle hallucine des sources alors qu'il n'aurait pas dû répondre).
- recall = 1.0 par convention (rien à rappeler).
- f1 = precision.

Ce module ne dépend ni de LLM ni d'embeddings : tests rapides et stables.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from rag.evaluation.golden import GoldenItem
from rag.interfaces.types import Answer


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


class CitationResult(BaseModel):
    """Détail par item — utile pour le rapport et le debugging."""

    item_id: str
    precision: float
    recall: float
    f1: float
    n_citations_emitted: int
    n_citations_correct: int


class CitationReport(BaseModel):
    """Métriques agrégées sur le golden."""

    n_items: int
    precision: float
    recall: float
    f1: float
    per_item: list[CitationResult] = Field(default_factory=list)


def _score_item(item: GoldenItem, answer: Answer) -> CitationResult:
    expected = set(item.expected_source_files)
    cited = [c.source_file for c in answer.citations]
    n_emitted = len(cited)

    # Cas out-of-domain : on attendait aucune source.
    if not expected:
        if n_emitted == 0:
            return CitationResult(
                item_id=item.id,
                precision=1.0,
                recall=1.0,
                f1=1.0,
                n_citations_emitted=0,
                n_citations_correct=0,
            )
        return CitationResult(
            item_id=item.id,
            precision=0.0,
            recall=1.0,
            f1=0.0,
            n_citations_emitted=n_emitted,
            n_citations_correct=0,
        )

    if n_emitted == 0:
        # Question in-domain mais réponse sans aucune citation : on a
        # complètement raté la consigne « citations forcées ».
        return CitationResult(
            item_id=item.id,
            precision=0.0,
            recall=0.0,
            f1=0.0,
            n_citations_emitted=0,
            n_citations_correct=0,
        )

    n_correct = sum(1 for src in cited if src in expected)
    precision = n_correct / n_emitted
    matched_expected = expected & set(cited)
    recall = len(matched_expected) / len(expected)
    return CitationResult(
        item_id=item.id,
        precision=precision,
        recall=recall,
        f1=_f1(precision, recall),
        n_citations_emitted=n_emitted,
        n_citations_correct=n_correct,
    )


def evaluate_citations(
    pairs: list[tuple[GoldenItem, Answer]],
) -> CitationReport:
    """Agrège la citation accuracy sur tout le batch.

    Args:
        pairs: liste de `(GoldenItem, Answer)` produits par le pipeline.

    Returns:
        Un `CitationReport` avec macro-moyennes (moyenne des scores per-item).
    """
    if not pairs:
        return CitationReport(n_items=0, precision=0.0, recall=0.0, f1=0.0)

    per_item = [_score_item(item, ans) for item, ans in pairs]
    n = len(per_item)
    return CitationReport(
        n_items=n,
        precision=sum(r.precision for r in per_item) / n,
        recall=sum(r.recall for r in per_item) / n,
        f1=sum(r.f1 for r in per_item) / n,
        per_item=per_item,
    )
