"""Budget (kill-switch) et piste d'audit — briques de production déterministes."""

import json

from agent import audit, executor, llm

# ── Budget / kill-switch ─────────────────────────────────────────────────────


def test_budget_blocks_call_before_network(monkeypatch):
    # max_calls=0 → chat() doit refuser AVANT même de joindre le client.
    called = {"n": 0}

    class _Spy:
        def generate(self, text):
            called["n"] += 1
            return "ne devrait pas arriver"

    monkeypatch.setattr(llm, "_client", lambda: _Spy())
    llm.start_run(max_calls=0, max_seconds=1000)
    try:
        llm.chat("bonjour")
        raise AssertionError("BudgetExceeded attendu")
    except llm.BudgetExceeded:
        pass
    assert called["n"] == 0  # aucun appel réseau consommé


def test_budget_exceeded_is_llm_unavailable_subclass():
    # Garantit que la dégradation gracieuse existante (except LLMUnavailable)
    # traite l'épuisement du budget sans code supplémentaire.
    assert issubclass(llm.BudgetExceeded, llm.LLMUnavailable)


def test_budget_allows_calls_under_limit(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda *_: None)
    monkeypatch.setattr(llm, "_tally", lambda *a, **k: None)

    class _Ok:
        def generate(self, text):
            return "ok"

    monkeypatch.setattr(llm, "_client", lambda: _Ok())
    llm.start_run(max_calls=2, max_seconds=1000)
    assert llm.chat("un") == "ok"
    # 2e appel : compteur non incrémenté (tally patché) → toujours sous la borne
    assert llm.chat("deux") == "ok"


def test_run_stops_whole_loop_on_budget(monkeypatch):
    # Budget épuisé pendant la boucle → arrêt immédiat, pas d'étape suivante tentée.
    def _budget_out(*a, **k):
        raise llm.BudgetExceeded("budget d'appels LLM atteint (0)")

    monkeypatch.setattr(executor, "choose_tool", _budget_out)
    monkeypatch.setattr(executor, "write_file", lambda *a, **k: "")
    monkeypatch.setattr(audit, "_write", lambda *a, **k: None)

    memory = executor.run("question", ["étape 1", "étape 2", "étape 3"])
    assert len(memory) == 1  # s'arrête à la 1re étape, ne tente pas les suivantes
    assert "budget" in memory[0]["result"].lower()


# ── Piste d'audit ────────────────────────────────────────────────────────────


def test_audit_writes_jsonl_trace(tmp_path, monkeypatch):
    log = tmp_path / "audit.jsonl"
    monkeypatch.setattr(audit, "AUDIT_FILE", log)
    monkeypatch.setattr(audit, "LOG_DIR", tmp_path)
    monkeypatch.setattr(audit, "_ENABLED", True)

    rid = audit.start_run("question de test")
    audit.event("security", allowed=True, category="ok")
    audit.step(1, "étape 1", "calculator", {"expression": "1+1"}, "2", ok=True)
    audit.end_run("ok", n_steps=1)

    lines = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
    events = [x["event"] for x in lines]
    assert events == ["run_start", "security", "step", "run_end"]
    assert all(x["run_id"] == rid for x in lines)
    assert lines[-1]["status"] == "ok"


def test_audit_never_raises_on_io_error(monkeypatch):
    # L'observabilité ne doit JAMAIS casser un run, même si l'écriture échoue.
    def _boom(*a, **k):
        raise OSError("disque plein")

    monkeypatch.setattr(audit.Path, "mkdir", _boom)
    monkeypatch.setattr(audit, "_ENABLED", True)
    audit.start_run("q")  # ne doit pas lever
    audit.event("step", tool="x")
    audit.end_run("ok")


def test_audit_noop_outside_run(monkeypatch):
    # event() hors d'un run ouvert = no-op silencieux (pas d'écriture).
    writes = []
    monkeypatch.setattr(audit, "_write", lambda rec: writes.append(rec))
    audit._current["run_id"] = None
    audit.event("orphan")
    assert writes == []


def test_audit_disabled_by_env(monkeypatch):
    monkeypatch.setattr(audit, "_ENABLED", False)
    writes = []
    monkeypatch.setattr(audit.Path, "mkdir", lambda *a, **k: writes.append("mkdir"))
    audit._write({"event": "x"})
    assert writes == []  # rien écrit quand désactivé
