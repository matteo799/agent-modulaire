"""Rapport d'évaluation (Markdown).

On reste en Markdown plutôt qu'en HTML : c'est lisible dans un PR comment
GitHub, dans n'importe quel terminal, et c'est ce que Langfuse expose en
lecture. Pas besoin de jinja ici, on construit le texte à la main.
"""

from __future__ import annotations

from .citation_metrics import CitationReport
from .golden import GoldenSet
from .ragas_metrics import RagasReport
from .retrieval_metrics import RetrievalReport


def _fmt_pct(value: float) -> str:
    return f"{value * 100:5.1f}%"


def _truncate(text: str, n: int = 80) -> str:
    return text if len(text) <= n else text[:n] + "…"


def _retrieval_per_item_table(
    retrieval: RetrievalReport,
    golden: GoldenSet | None,
) -> list[str]:
    """Tableau Markdown une-ligne-par-question avec statut et sources lisibles."""
    if not retrieval.per_item:
        return []

    golden_by_id = {item.id: item for item in golden.items} if golden else {}

    lines = [
        "### Détail par question",
        "",
        "| ID | Question | hit | RR | ms | Sources attendues | Sources reçues |",
        "|---|---|:---:|:---:|---:|---|---|",
    ]
    for r in retrieval.per_item:
        gi = golden_by_id.get(r.item_id)
        question = _truncate(gi.question, 60) if gi else r.item_id
        expected_ids = set(gi.expected_chunk_ids) if gi else set()
        expected_files = gi.expected_source_files if gi else []

        hit_icon = "✓" if r.hit_at_k else "✗"
        rr_str = f"{r.reciprocal_rank:.2f}"
        ms_str = f"{r.latency_ms:.0f}"

        # Expected: readable source file names from golden
        expected_str = ", ".join(expected_files) if expected_files else "hors-domaine"

        # Received: source_file p.N, bold = chunk attendu trouvé
        received_parts: list[str] = []
        for rid, label in zip(r.retrieved_ids, r.retrieved_labels, strict=True):
            if rid in expected_ids:
                received_parts.append(f"**{label}**")
            else:
                received_parts.append(label)
        received_str = " → ".join(received_parts) if received_parts else "—"

        lines.append(
            f"| {r.item_id} | {question} | {hit_icon} | {rr_str}"
            f" | {ms_str} | {expected_str} | {received_str} |"
        )

    lines.append("")
    return lines


def build_markdown_report(
    *,
    golden_version: str,
    retrieval: RetrievalReport | None = None,
    golden: GoldenSet | None = None,
    citation: CitationReport | None = None,
    ragas: RagasReport | None = None,
    thresholds_passed: bool | None = None,
) -> str:
    """Compose un rapport markdown à partir des sous-reports disponibles.

    Tous les arguments sont optionnels : on ne montre que ce qui a tourné.
    Passer `golden` active le tableau détaillé par question.
    """
    lines: list[str] = [
        "# Eval report",
        "",
        f"Golden set : `{golden_version}`",
        "",
    ]

    if thresholds_passed is not None:
        verdict = "PASS" if thresholds_passed else "FAIL"
        lines += [f"**Verdict : {verdict}**", ""]

    if retrieval is not None:
        lines += [
            "## Retrieval",
            "",
            f"- items évalués : {retrieval.n_items}",
            f"- k : {retrieval.k}",
            f"- hit@k         : {_fmt_pct(retrieval.hit_rate)}",
            f"- mean_recall   : {_fmt_pct(retrieval.mean_recall)}",
            f"- MRR           : {retrieval.mrr:.3f}",
            f"- latence moy.  : {retrieval.mean_latency_ms:.0f} ms",
            f"- latence p50   : {retrieval.p50_latency_ms:.0f} ms",
            f"- latence p95   : {retrieval.p95_latency_ms:.0f} ms",
            f"- latence max   : {retrieval.max_latency_ms:.0f} ms",
            "",
        ]
        lines += _retrieval_per_item_table(retrieval, golden)

    if citation is not None:
        lines += [
            "## Citations",
            "",
            f"- items évalués : {citation.n_items}",
            f"- precision : {_fmt_pct(citation.precision)}",
            f"- recall    : {_fmt_pct(citation.recall)}",
            f"- F1        : {_fmt_pct(citation.f1)}",
            "",
        ]

    if ragas is not None:
        lines += [
            "## RAGAS",
            "",
            f"- items évalués : {ragas.n_items}",
            f"- faithfulness    : {_fmt_pct(ragas.faithfulness)}",
            f"- answer_relevancy : {_fmt_pct(ragas.answer_relevancy)}",
            "",
        ]

    return "\n".join(lines).rstrip() + "\n"
