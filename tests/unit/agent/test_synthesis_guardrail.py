"""Garde-fou hors-sujet : refuser SEULEMENT si le RAG était la seule source.

Régression : un fonds Amundi déclenche parfois un rag_search vide (il n'est pas
dans le corpus finance) ; le refus ne doit pas jeter les données structurées
(fund_summary, metric_*) qui répondent déjà à la question.
"""
import pytest

import main


def test_ambiguous_fund_asks_to_choose(monkeypatch):
    # find_fund ambigu → on renvoie la liste + demande de préciser, sans appeler le LLM.
    monkeypatch.setattr(main.llm, "chat", lambda *a, **k: pytest.fail("le LLM ne doit pas être appelé"))
    memory = [
        _mem("find_fund",
             "Plusieurs fonds correspondent à « cash eur » (préciser lequel) :\n"
             "  - LU0568620727 — AMUNDI FUNDS CASH EUR - G2\n"
             "  - LU0568620560 — AMUNDI FUNDS CASH EUR - A2"),
        _mem("fund_summary", "Fiche LU0568620727 : ..."),  # part choisie au hasard — à ignorer
    ]
    out = main.synthesize("parle-moi du fonds cash eur", memory)
    assert "LU0568620727" in out and "LU0568620560" in out
    assert "préciser" in out.lower()


def test_unique_fund_does_not_trigger_disambiguation(monkeypatch):
    monkeypatch.setattr(main.llm, "chat", lambda *a, **k: "RÉPONSE")
    memory = [
        _mem("find_fund", "Fonds trouvé : FR0010750869 — AMUNDI ACTIONS FRANCE RESPONSABLE - P (D)"),
        _mem("fund_summary", "Fiche FR0010750869 : ..."),
    ]
    assert main.synthesize("le fonds X", memory) == "RÉPONSE"


def test_refuse_when_rag_only_and_empty():
    memory = [{"tool": "rag_search", "result": "Aucun passage pertinent trouvé dans les documents."}]
    assert main.synthesize("question", memory).startswith("Les documents fournis ne permettent pas")


def _mem(tool, result, step="étape"):
    """Entrée de mémoire complète (les helpers de synthèse lisent aussi step/args)."""
    return {"step": step, "tool": tool, "raison": "", "args": {}, "result": result}


def test_no_refuse_when_structured_result_present(monkeypatch):
    # rag_search vide MAIS fund_summary a renvoyé de vraies données → on synthétise.
    monkeypatch.setattr(main.llm, "chat", lambda *a, **k: "RÉPONSE SYNTHÉTISÉE")
    memory = [
        _mem("rag_search", "Aucun passage pertinent trouvé dans les documents."),
        _mem("fund_summary", "Fiche FR0010750869 : Nom : AMUNDI ACTIONS FRANCE..."),
    ]
    assert main.synthesize("profil du fonds", memory) == "RÉPONSE SYNTHÉTISÉE"


def test_structured_detector_ignores_errors_and_writes():
    only_noise = [
        _mem("rag_search", "Aucun passage pertinent"),
        _mem("metric_sharpe", "Erreur : calcul impossible"),
        _mem("write_file", "Fichier écrit : workspace/x.md"),
    ]
    assert main._has_structured_result(only_noise) is False
    with_data = [*only_noise, _mem("fund_stats", "profil risque/rendement : ...")]
    assert main._has_structured_result(with_data) is True
