"""OllamaClient — adapter HTTP pour un serveur Ollama local.

Ollama expose une API REST sur `http://localhost:11434/api/generate`. On
parle JSON et c'est tout — pas de SDK Python à charger (ollama propose un
client officiel mais il ajoute une dep pour rien : httpx suffit).

Choix d'implémentation :

- Synchrone (httpx.Client) : l'orchestration CRAG est synchrone au POC.
  Si on passe en async plus tard, on ajoutera un `OllamaAsyncClient`
  séparé qui implémente le même Protocol.
- Timeouts généreux (60s par défaut) : Mistral 7B sur CPU peut prendre
  20-30s pour générer 500 tokens. Configurable par kwargs.
- Retry tenacity sur les erreurs réseau transitoires uniquement (pas sur
  les 4xx : ils signalent un bug d'appel, on veut le voir tout de suite).
- `count_tokens` : Ollama n'expose pas d'endpoint de tokenisation. On
  utilise une approximation chars/4 qui est correcte à ±20% pour Mistral.
  Suffit pour du budgeting de prompt, pas pour de la facturation.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any, cast

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from rag.utils.logging import get_logger

_log = get_logger(__name__)

# Approximation de tokenisation : Mistral / LLaMA → ~4 chars par token.
# Référence : https://github.com/openai/tiktoken#how-strings-are-counted
_CHARS_PER_TOKEN = 4


class OllamaClient:
    """Adapter HTTP pour Ollama. Implémente le `LLMClient` Protocol."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "mistral:7b-instruct",
        *,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        timeout_s: float = 60.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        # `httpx.Client` est paresseusement créé pour ne pas ouvrir de socket
        # à l'import du module (utile pour les tests qui ne génèrent pas).
        self._client: httpx.Client | None = None
        self._timeout = httpx.Timeout(timeout_s, connect=10.0)

    # --- Protocol -----------------------------------------------------------

    @property
    def model_id(self) -> str:
        return self._model

    def generate(self, prompt: str, **kwargs: Any) -> str:
        payload = self._build_chat_payload(prompt, stream=False, **kwargs)
        resp = self._post_with_retry("/api/chat", payload)
        data = resp.json()
        text = data.get("message", {}).get("content", "")
        if not isinstance(text, str):
            raise RuntimeError(f"unexpected ollama payload: {data!r}")
        return text

    def stream_generate(self, prompt: str, **kwargs: Any) -> Iterator[str]:
        payload = self._build_chat_payload(prompt, stream=True, **kwargs)
        client = self._ensure_client()
        with client.stream("POST", "/api/chat", json=payload) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                event = json.loads(line)
                chunk = event.get("message", {}).get("content", "")
                if chunk:
                    yield cast(str, chunk)
                if event.get("done"):
                    break

    def count_tokens(self, text: str) -> int:
        # Approximation chars/4 + 1 (le +1 évite 0 sur un texte non-vide).
        if not text:
            return 0
        return max(1, len(text) // _CHARS_PER_TOKEN + 1)

    # --- Internals ----------------------------------------------------------

    def _build_chat_payload(self, prompt: str, *, stream: bool, **kwargs: Any) -> dict[str, Any]:
        # /api/chat : le prompt devient un message user unique.
        options: dict[str, Any] = {
            "temperature": float(kwargs.get("temperature", self._temperature)),
            "num_predict": int(kwargs.get("max_tokens", self._max_tokens)),
        }
        if "top_p" in kwargs:
            options["top_p"] = float(kwargs["top_p"])
        if "stop" in kwargs:
            options["stop"] = list(kwargs["stop"])

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": stream,
            "options": options,
        }
        # `think: false` désactive la réflexion interne des modèles thinking
        # (DeepSeek-R1, etc.) pour les tâches d'extraction structurée rapide.
        if "think" in kwargs:
            payload["think"] = bool(kwargs["think"])
        return payload

    @retry(
        reraise=True,
        retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout)),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5.0),
        stop=stop_after_attempt(3),
    )
    def _post_with_retry(self, path: str, payload: dict[str, Any]) -> httpx.Response:
        client = self._ensure_client()
        _log.debug("ollama request", path=path, model=self._model)
        resp = client.post(path, json=payload)
        # `raise_for_status` ne retry pas : un 4xx est un bug d'appel.
        resp.raise_for_status()
        return resp

    def _ensure_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(base_url=self._base_url, timeout=self._timeout)
        return self._client

    # Permet aux tests d'injecter un transport httpx custom (MockTransport).
    # Pas dans le Protocol — c'est un détail d'implémentation, mais on l'expose
    # explicitement pour rester testable sans monkeypatcher.
    def _set_transport(self, transport: httpx.BaseTransport) -> None:
        self._client = httpx.Client(
            base_url=self._base_url, timeout=self._timeout, transport=transport
        )
