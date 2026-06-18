"""Entrypoint `python -m tests.rag_eval.run` (M6.5).

Charge `tests/eval.yaml` (override-able par `--config`), exécute les
métriques activées, écrit un rapport markdown, et exit avec code != 0
si un threshold est manqué (utilisé par la CI pour bloquer un PR).

Volontairement minimal : pas d'argparse fancy, pas de framework de
benchmarking. C'est un script de validation, pas un produit.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from rag.config.factory import build_retriever
from rag.config.settings import load_settings
from .golden import GoldenSet, load_golden_set
from .report import build_markdown_report
from .retrieval_metrics import (
    RetrievalReport,
    evaluate_retrieval,
)

# --- schéma config --------------------------------------------------------


class _RetrievalCfg(BaseModel):
    k: int = 5
    thresholds: dict[str, float] = Field(default_factory=dict)


class _CitationCfg(BaseModel):
    thresholds: dict[str, float] = Field(default_factory=dict)


class _RagasCfg(BaseModel):
    enabled: bool = False
    thresholds: dict[str, float] = Field(default_factory=dict)


class _ReportCfg(BaseModel):
    output: Path = Path("eval_report.md")


class EvalConfig(BaseModel):
    """Schéma de `tests/eval.yaml`."""

    golden_set: Path
    retrieval: _RetrievalCfg = _RetrievalCfg()
    citation: _CitationCfg = _CitationCfg()
    ragas: _RagasCfg = _RagasCfg()
    report: _ReportCfg = _ReportCfg()


def load_eval_config(path: Path | str) -> EvalConfig:
    p = Path(path)
    with p.open("r", encoding="utf-8") as fp:
        raw = yaml.safe_load(fp) or {}
    return EvalConfig.model_validate(raw)


# --- threshold checking ---------------------------------------------------


def _check_thresholds(
    label: str, scores: dict[str, float], thresholds: dict[str, float]
) -> list[str]:
    """Retourne la liste des messages d'échec (vide = tout passe)."""
    failures: list[str] = []
    for metric, min_value in thresholds.items():
        if metric not in scores:
            failures.append(f"[{label}] métrique '{metric}' absente du rapport")
            continue
        if scores[metric] < min_value:
            failures.append(f"[{label}] {metric}={scores[metric]:.3f} < threshold {min_value:.3f}")
    return failures


def _retrieval_scores(report: RetrievalReport) -> dict[str, float]:
    return {
        "hit_rate": report.hit_rate,
        "mean_recall": report.mean_recall,
        "mrr": report.mrr,
    }


# --- runner ---------------------------------------------------------------


def run(config: EvalConfig, *, golden: GoldenSet | None = None) -> tuple[str, list[str]]:
    """Lance l'éval définie par `config`.

    Args:
        config: configuration chargée depuis YAML.
        golden: golden set déjà chargé (utile pour les tests qui veulent
            éviter l'I/O). Si None, on lit depuis `config.golden_set`.

    Returns:
        `(markdown_report, failures)` où `failures` est la liste des
        thresholds non atteints (vide si tout passe).
    """
    gs = golden if golden is not None else load_golden_set(config.golden_set)
    settings = load_settings()

    failures: list[str] = []

    # --- retrieval ---
    retriever = build_retriever(settings)
    retrieval_report = evaluate_retrieval(retriever, gs, k=config.retrieval.k)
    failures += _check_thresholds(
        "retrieval", _retrieval_scores(retrieval_report), config.retrieval.thresholds
    )

    # --- citation + ragas : à câbler quand on aura un runner de graphe ---
    # Pour l'instant, le runner CLI ne lance que les métriques retrieval
    # (LLM-free → toujours possible en CI). Le mode `--full` qui exécute
    # le graphe complet sera une PR séparée — il aura besoin d'Ollama up
    # côté GitHub runner, ce qui mérite sa propre discussion.

    md = build_markdown_report(
        golden_version=gs.version,
        retrieval=retrieval_report,
        golden=gs,
        thresholds_passed=not failures,
    )
    return md, failures


# --- entrypoint -----------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    # Éval = modèle économe par défaut (n'a d'effet que si RAGAS est activé ;
    # les métriques retrieval ne touchent pas le LLM). Surchargeable par env.
    os.environ.setdefault("RAG__LLM__OPENAI__MODEL", "claude-haiku-4-5")
    parser = argparse.ArgumentParser(prog="tests.rag_eval.run")
    parser.add_argument(
        "--config",
        default="tests/eval.yaml",
        help="chemin vers le fichier de config eval (défaut: tests/eval.yaml)",
    )
    args = parser.parse_args(argv)

    cfg = load_eval_config(args.config)
    md, failures = run(cfg)

    cfg.report.output.write_text(md, encoding="utf-8")
    print(md)
    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(f" - {f}")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
