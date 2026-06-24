"""Tests de la sélection de métrique + clarification (LLM monkeypatché)."""

from agent.finance import select

# ── Pré-filtre lexical (pas de LLM) ───────────────────────────────────────


def test_looks_like_metric_query():
    assert select.looks_like_metric_query("Quel est le ratio de Sharpe de ce fonds ?")
    assert select.looks_like_metric_query("une métrique qui ne pénalise pas la hausse")
    assert not select.looks_like_metric_query("Qui est le dépositaire du fonds FR0010544791 ?")


# ── Sélection non ambiguë : aucune clarification demandée ─────────────────


def test_downside_intent_resolves_to_sortino_without_asking(monkeypatch):
    monkeypatch.setattr(
        select.llm,
        "chat_json",
        lambda *a, **k: {
            "metric": "sortino",
            "ambiguous": False,
            "rationale": "volatilité à la baisse",
            "options": [],
        },
    )

    def _must_not_ask(question, options):  # pragma: no cover
        raise AssertionError("ask_fn ne doit pas être appelé sans ambiguïté")

    out = select.select_metric("je crains surtout les baisses", ask_fn=_must_not_ask)
    assert out["metric"] == "sortino"


# ── Sélection ambiguë : clarification déclenchée ──────────────────────────


def test_ambiguous_triggers_clarification(monkeypatch):
    monkeypatch.setattr(
        select.llm,
        "chat_json",
        lambda *a, **k: {
            "metric": None,
            "ambiguous": True,
            "rationale": "",
            "question": "Sharpe ou Sortino ?",
            "options": ["sharpe", "sortino"],
        },
    )
    asked = {}

    def _ask(question, options):
        asked["question"] = question
        asked["options"] = options
        return "sortino"

    out = select.select_metric("la meilleure métrique rendement/risque", ask_fn=_ask)
    assert out["metric"] == "sortino"
    assert asked["options"] == ["sharpe", "sortino"]
    assert "Sharpe" in asked["question"]


def test_ambiguous_with_missing_options_defaults_to_sharpe_sortino(monkeypatch):
    monkeypatch.setattr(
        select.llm,
        "chat_json",
        lambda *a, **k: {"metric": None, "ambiguous": True, "options": []},
    )
    out = select.select_metric("métrique rendement/risque ?", ask_fn=lambda q, o: o[0])
    assert out["metric"] == "sharpe"  # 1re option du défaut [sharpe, sortino]


def test_unknown_metric_falls_back(monkeypatch):
    monkeypatch.setattr(
        select.llm,
        "chat_json",
        lambda *a, **k: {"metric": "inconnue", "ambiguous": False, "options": []},
    )
    out = select.select_metric("ratio bidon", ask_fn=lambda q, o: o[0])
    assert out["metric"] in select.CATALOG


def test_auto_ask_picks_first_option():
    assert select.auto_ask("Sharpe ou Sortino ?", ["sharpe", "sortino"]) == "sharpe"
