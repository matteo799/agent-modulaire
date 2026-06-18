"""OpenAIClient — adapter pour toute API OpenAI-compatible avec clé Bearer.

Couvre l'API OpenAI elle-même comme les passerelles compatibles (ex.
`https://api.meai.cloud/v1`, qui sert des modèles Claude au format OpenAI).
On parle directement à `/v1/chat/completions` avec httpx — pas de SDK openai,
cohérent avec le reste du projet.

Seule différence avec `LMStudioClient` : on envoie un header
`Authorization: Bearer <api_key>` (les passerelles cloud l'exigent).

La clé NE doit JAMAIS être committée : elle vient de la config via la variable
d'environnement `RAG__LLM__OPENAI__API_KEY` (ou d'un `.env` gitignoré).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from rag.utils.logging import get_logger

_log = get_logger(__name__)

_CHARS_PER_TOKEN = 4


class OpenAIClient:
    """Adapter OpenAI-compatible. Implémente le `LLMClient` Protocol."""

    def __init__(
        self,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        api_key: str = "",
        *,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        timeout_s: float = 120.0,
    ) -> None:
        # On retire un éventuel /v1 final : on l'ajoute nous-mêmes dans le path
        # (`/v1/chat/completions`), comme pour LM Studio.
        self._base_url = base_url.rstrip("/").removesuffix("/v1")
        self._model = model
        self._api_key = api_key
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._client: httpx.Client | None = None
        self._timeout = httpx.Timeout(timeout_s, connect=10.0)

    # --- Protocol -----------------------------------------------------------

    @property
    def model_id(self) -> str:
        return self._model

    def generate(self, prompt: str, **kwargs: Any) -> str:
        payload = self._build_payload(prompt, stream=False, **kwargs)
        resp = self._post_with_retry("/v1/chat/completions", payload)
        data = resp.json()
        try:
            message = data["choices"][0]["message"]
            # Modèles à raisonnement (Claude thinking, DeepSeek-R1…) : si `content`
            # est vide, on retombe sur `reasoning_content` pour ne pas bloquer.
            content = message.get("content") or message.get("reasoning_content") or ""
            return str(content)
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"unexpected openai response: {data!r}") from exc

    def stream_generate(self, prompt: str, **kwargs: Any) -> Iterator[str]:
        payload = self._build_payload(prompt, stream=True, **kwargs)
        client = self._ensure_client()
        with client.stream("POST", "/v1/chat/completions", json=payload) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                line = line.strip()
                if not line or not line.startswith("data:"):
                    continue
                raw = line[len("data:") :].strip()
                if raw == "[DONE]":
                    break
                try:
                    event = json.loads(raw)
                    delta = event["choices"][0].get("delta", {})
                    chunk = delta.get("content", "")
                    if chunk:
                        yield str(chunk)
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        return max(1, len(text) // _CHARS_PER_TOKEN + 1)

    # --- Internals ----------------------------------------------------------

    def _build_payload(self, prompt: str, *, stream: bool, **kwargs: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": float(kwargs.get("temperature", self._temperature)),
            "max_tokens": int(kwargs.get("max_tokens", self._max_tokens)),
            "stream": stream,
        }
        if "stop" in kwargs:
            payload["stop"] = list(kwargs["stop"])
        return payload

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    @retry(
        reraise=True,
        retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout)),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5.0),
        stop=stop_after_attempt(3),
    )
    def _post_with_retry(self, path: str, payload: dict[str, Any]) -> httpx.Response:
        client = self._ensure_client()
        _log.debug("openai request", path=path, model=self._model)
        resp = client.post(path, json=payload)
        resp.raise_for_status()
        return resp

    def _ensure_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self._base_url, timeout=self._timeout, headers=self._headers()
            )
        return self._client

    def _set_transport(self, transport: httpx.BaseTransport) -> None:
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=self._timeout,
            headers=self._headers(),
            transport=transport,
        )
