"""Langfuse callback handler (M6.6) — tracing du graphe CRAG.

Langfuse expose un callback LangChain (`langfuse.callback.CallbackHandler`)
qui s'attache aux invocations LangGraph via `config={"callbacks": [...]}`.
Chaque nœud du graphe devient un span, chaque appel LLM est tracké, on a
les latences et les prompts visibles dans l'UI Langfuse.

Sécurité : les credentials Langfuse ne sont JAMAIS hardcodés. On les lit
depuis `Settings.observability` (qui les chope depuis l'env via
pydantic-settings → `RAG__OBSERVABILITY__LANGFUSE_PUBLIC_KEY` etc.).

Politique d'activation :
- `observability.langfuse_enabled == False` → `build_langfuse_handler`
  retourne `None`, on ne charge pas la lib, on ne fait rien.
- `True` + lib absente → on log un warning et on retourne `None` pour ne
  pas casser le pipeline. C'est volontairement non-fatal : Langfuse est un
  bonus, pas un bloquant.
- `True` + lib présente → on construit le handler.
"""

from __future__ import annotations

from typing import Any

from rag.config.settings import Settings
from rag.utils.logging import get_logger

_log = get_logger(__name__)


def build_langfuse_handler(settings: Settings) -> Any | None:
    """Construit le `CallbackHandler` Langfuse, ou None si désactivé.

    Le type de retour est `Any` parce qu'on ne dépend pas du module
    `langfuse` dans la signature (sinon mypy se plaint sur les setups où
    l'extra n'est pas installé).
    """
    obs = settings.observability
    if not obs.langfuse_enabled:
        return None

    try:
        # Import paresseux : on tolère que l'extra `observability` ne soit
        # pas installé en CI / dev sans tracing.
        from langfuse.callback import CallbackHandler  # type: ignore[import-not-found]
    except ImportError:
        _log.warning(
            "langfuse_enabled=True mais le module `langfuse` n'est pas installé. "
            "Pour activer le tracing : `pip install -e '.[observability]'`."
        )
        return None

    # Les credentials viennent de l'env via pydantic-settings.
    # On n'a pas (encore) de champs dédiés dans Settings → on tire d'env vars
    # standard `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` que la lib lit
    # nativement si on ne passe rien explicitement.
    handler = CallbackHandler(host=obs.langfuse_host)
    _log.info("langfuse handler initialised", host=obs.langfuse_host)
    return handler
