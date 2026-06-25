"""Robustesse réseau : un appel LLM en échec ne tue pas le run."""

import httpx
import pytest

from agent import executor, llm


def test_chat_raises_typed_exception_after_retries(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda *_: None)  # pas d'attente réelle

    class _Boom:
        def generate(self, text):
            raise httpx.RemoteProtocolError("connexion coupée par le serveur")

    monkeypatch.setattr(llm, "_client", lambda: _Boom())
    with pytest.raises(llm.LLMUnavailable):
        llm.chat("bonjour")


def test_chat_recovers_after_transient_failure(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda *_: None)
    calls = {"n": 0}

    class _Flaky:
        def generate(self, text):
            calls["n"] += 1
            if calls["n"] < 2:
                raise httpx.ReadTimeout("lent")
            return "ok"

    monkeypatch.setattr(llm, "_client", lambda: _Flaky())
    assert llm.chat("salut") == "ok"
    assert calls["n"] == 2


def test_run_continues_when_a_step_loses_the_llm(monkeypatch):
    # choose_tool échoue (LLM down) à chaque étape → la boucle ne plante pas.
    def _down(*a, **k):
        raise llm.LLMUnavailable("réseau indisponible")

    monkeypatch.setattr(executor, "choose_tool", _down)
    monkeypatch.setattr(executor, "write_file", lambda *a, **k: "")  # pas d'I/O réel

    memory = executor.run("question", ["étape 1", "étape 2"])
    assert len(memory) == 2
    assert all("indisponible" in m["result"] for m in memory)
