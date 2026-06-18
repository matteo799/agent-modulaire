"""Chargeur de prompts Jinja2.

Tous les prompts du projet vivent dans `src/rag/prompts/*.j2`. Aucun prompt
n'est jamais en chaîne inline dans du code Python — c'est une règle dure
(`CLAUDE.md` §3.4).

Pourquoi Jinja2 et pas autre chose :
- Standard Python, MIT, déjà transitif via langchain.
- Auto-escape désactivé volontairement : on rend du texte LLM, pas du HTML.
- StrictUndefined : si on oublie une variable dans le call site, ça pète
  immédiatement plutôt que de produire un prompt trompeur avec des trous.

Utilisation :
    from rag.prompts import render
    prompt = render("grade_documents", query="SCPI", doc="La SCPI investit dans…")
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

_PROMPTS_DIR = Path(__file__).parent


@lru_cache(maxsize=64)
def _get_env() -> Any:
    """Crée le `jinja2.Environment` une seule fois par process.

    Import paresseux : tant qu'on ne rend pas de prompt, on n'importe pas
    Jinja2 (utile pour les tests qui ne touchent pas au CRAG).
    """
    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    return Environment(
        loader=FileSystemLoader(str(_PROMPTS_DIR)),
        autoescape=False,  # pas de HTML, c'est du prompt
        undefined=StrictUndefined,  # plante si une variable manque
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render(name: str, **kwargs: Any) -> str:
    """Charge `<name>.j2` et le rend avec les kwargs passés.

    Args:
        name: nom du template sans extension (ex. "grade_documents").
        **kwargs: variables passées au template. Toute variable utilisée par
            le template et absente d'ici lèvera `UndefinedError`.

    Returns:
        Le prompt final, prêt à être envoyé au LLM.
    """
    template = _get_env().get_template(f"{name}.j2")
    rendered: str = template.render(**kwargs)
    return rendered
