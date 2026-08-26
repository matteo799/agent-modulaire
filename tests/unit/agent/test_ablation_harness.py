"""Le harness d'ablation : métriques déterministes et bras exécutables sans réseau.

Ces tests valident le harness lui-même, pas les modèles. Ils tournent avec un LLM
factice, ce qui permet de vérifier que les cinq bras s'exécutent réellement et que
les mesures d'ancrage et de refus se comportent comme annoncé.
"""

import importlib.util
from pathlib import Path

import pytest

from agent import executor, llm

ROOT = Path(__file__).resolve().parents[3]


def _load_ablation():
    spec = importlib.util.spec_from_file_location(
        "run_ablation", ROOT / "tests" / "agent_eval" / "run_ablation.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ab = _load_ablation()


# ── Métriques déterministes ──────────────────────────────────────────────────


def test_numbers_ignores_small_integers_and_normalises_separators():
    # 7 est ignoré (< 10) ; la virgule décimale et l'espace millier sont normalisés.
    assert ab._numbers("SRI de 7, frais 1,25 %, encours 1 250 000 EUR") == ["1.25", "1250000"]


def test_ungrounded_numbers_flags_only_what_no_source_supports():
    answer = "Les frais sont de 1,25 % et le Sharpe de 0,87."
    sources = "Frais courants : 1,25 %"
    question = "Quels sont les frais ?"
    # 1.25 vient des sources ; 0.87 n'apparaît nulle part → non étayé.
    assert ab._ungrounded_numbers(answer, sources, question) == ["0.87"]


def test_number_present_in_the_question_counts_as_grounded():
    assert ab._ungrounded_numbers("Sur 36 mois.", "", "Performance sur 36 mois ?") == []


def test_refusal_detection_matches_the_grounded_synthesis_wording():
    assert ab._is_refusal("Les documents fournis ne permettent pas de répondre.")
    assert not ab._is_refusal("Les frais courants sont de 1,25 %.")


def test_aggregate_counts_coverage_refusals_and_ungrounded():
    rows = [
        {"covered": True, "refusal_ok": None, "ungrounded": [], "latency": 1.0,
         "tokens": 10, "llm_calls": 2, "error": ""},
        {"covered": False, "refusal_ok": True, "ungrounded": ["4.2"], "latency": 3.0,
         "tokens": 20, "llm_calls": 4, "error": "boom"},
    ]
    a = ab.aggregate(rows)
    assert a["coverage"] == "1/2"
    assert a["refusal"] == "1/1"
    assert a["ungrounded_q"] == 1 and a["ungrounded_n"] == 1
    assert a["tokens"] == 30 and a["errors"] == 1
    assert a["latency"] == pytest.approx(2.0)


# ── Les cinq bras s'exécutent réellement, sans réseau ────────────────────────


@pytest.fixture
def stub_llm(monkeypatch):
    """LLM factice : plan à une étape, choix d'outil déterministe, synthèse fixe."""
    monkeypatch.setattr(llm, "chat", lambda *a, **k: "Frais courants : 1,25 %.")
    monkeypatch.setattr(
        llm,
        "chat_json",
        lambda prompt, **k: (
            {"steps": ["Chercher les frais"]}
            if "Décompose" in prompt
            else {"raison": "test", "tool": "rag_search", "args": {"query": "frais"}}
        ),
    )
    monkeypatch.setattr(ab, "rag_search", lambda *a, **k: "Frais courants : 1,25 %")
    monkeypatch.setitem(
        executor.TOOLS["rag_search"], "function", lambda **kw: "Frais courants : 1,25 %"
    )
    monkeypatch.setattr(executor, "write_file", lambda *a, **k: "")  # pas d'I/O réel


@pytest.mark.parametrize("key", ["A", "B", "C", "D", "E"])
def test_every_arm_runs_and_reports_its_tools(stub_llm, key):
    item = {
        "id": "t-01",
        "question": "Quels sont les frais courants ?",
        "category": "lookup",
        "expected_tools": ["rag_search"],
    }
    row = ab.run_one(key, item)
    assert row["error"] == "", f"le bras {key} a échoué : {row['error']}"
    assert row["used"] == ["rag_search"]
    assert row["covered"] is True
    assert row["ungrounded"] == []  # 1,25 vient bien de la source


def test_arm_c_disables_the_retry_loop(monkeypatch, stub_llm):
    """C doit exécuter chaque étape une seule fois, même sur un résultat en erreur."""
    attempts = {"n": 0}

    def _always_failing(**kwargs):
        attempts["n"] += 1
        return "Erreur : outil indisponible"

    monkeypatch.setitem(executor.TOOLS["rag_search"], "function", _always_failing)
    ab.run_one("C", {"id": "t", "question": "frais ?", "category": "lookup"})
    assert attempts["n"] == 1, "max_retries=0 doit interdire toute reprise"


def test_arm_d_retries_once_on_error(monkeypatch, stub_llm):
    attempts = {"n": 0}

    def _always_failing(**kwargs):
        attempts["n"] += 1
        return "Erreur : outil indisponible"

    monkeypatch.setitem(executor.TOOLS["rag_search"], "function", _always_failing)
    ab.run_one("D", {"id": "t", "question": "frais ?", "category": "lookup"})
    assert attempts["n"] == 2, "la réflexion déterministe doit déclencher une reprise"


def test_out_of_corpus_question_is_scored_on_refusal(stub_llm, monkeypatch):
    monkeypatch.setattr(
        llm, "chat", lambda *a, **k: "Les documents fournis ne permettent pas de répondre."
    )
    row = ab.run_one(
        "A", {"id": "t", "question": "Météo à Tokyo ?", "category": "hors-corpus"}
    )
    assert row["refusal_ok"] is True


def test_llm_judge_falls_back_to_the_deterministic_rule_when_llm_is_down(monkeypatch):
    monkeypatch.setattr(
        llm, "chat_json", lambda *a, **k: (_ for _ in ()).throw(llm.LLMUnavailable("down"))
    )
    # Résultat valide → la règle déterministe le déclare suffisant malgré le juge KO.
    assert executor.llm_reflect("étape", "résultat correct")["sufficient"] is True
    assert executor.llm_reflect("étape", "Erreur : rien")["sufficient"] is False
