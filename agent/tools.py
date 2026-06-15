"""Registre d'outils : l'agent connaît ses capacités via TOOLS."""
from pathlib import Path

from agent.rag import rag_search

WORKSPACE_DIR = Path(__file__).resolve().parent.parent / "workspace"


def read_file(path: str) -> str:
    """Lit un fichier du workspace (ou un chemin relatif au projet)."""
    candidate = WORKSPACE_DIR / path
    if not candidate.exists():
        candidate = Path(path)
    if not candidate.exists():
        return f"Erreur : fichier introuvable : {path}"
    return candidate.read_text(encoding="utf-8")


def write_file(path: str, content: str) -> str:
    """Écrit un fichier dans le workspace de l'agent."""
    path = path.removeprefix("workspace/")
    target = WORKSPACE_DIR / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Fichier écrit : workspace/{path} ({len(content)} caractères)"


def calculator(expression: str) -> str:
    """Évalue une expression arithmétique simple."""
    allowed = set("0123456789+-*/(). %")
    if not set(expression) <= allowed:
        return f"Erreur : expression non autorisée : {expression}"
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as exc:
        return f"Erreur de calcul : {exc}"


TOOLS = {
    "rag_search": {
        "function": rag_search,
        "description": "Recherche sémantique dans les documents internes (dossier documents/). "
                       "Arguments : query (str), top_k (int, optionnel).",
    },
    "read_file": {
        "function": read_file,
        "description": "Lit un fichier texte. Arguments : path (str).",
    },
    "write_file": {
        "function": write_file,
        "description": "Écrit un fichier dans le workspace. Arguments : path (str), content (str).",
    },
    "calculator": {
        "function": calculator,
        "description": "Évalue une expression arithmétique. Arguments : expression (str).",
    },
}


def tools_catalog() -> str:
    """Description des outils, injectée dans les prompts de sélection."""
    return "\n".join(f"- {name} : {spec['description']}" for name, spec in TOOLS.items())
