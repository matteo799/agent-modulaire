"""Registre d'outils : l'agent connaît ses capacités via TOOLS."""
from pathlib import Path

from agent.rag import rag_search, list_sources

WORKSPACE_DIR = Path(__file__).resolve().parent.parent / "workspace"
DOCUMENTS_DIR = Path(__file__).resolve().parent.parent / "documents"


def read_file(path: str) -> str:
    """Lit un fichier depuis le workspace, les documents sources ou un chemin direct."""
    name = path.removeprefix("workspace/").removeprefix("documents/")
    for candidate in (WORKSPACE_DIR / name, DOCUMENTS_DIR / name, Path(path)):
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    return f"Erreur : fichier introuvable : {path}"


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
                       "À utiliser pour TOUTE information à retrouver dans les documents "
                       "(faits, chiffres, dates). NE PAS deviner de nom de fichier. "
                       "Si la réponse indique qu'aucun passage pertinent n'existe, c'est que "
                       "les documents ne couvrent pas le sujet : ne pas inventer. "
                       "Arguments : query (str), top_k (int, optionnel), "
                       "source (str, optionnel : restreint la recherche à un document, ex. un ISIN).",
    },
    "list_documents": {
        "function": list_sources,
        "description": "Liste les documents/fonds disponibles dans documents/. Sans argument. "
                       "Utile en première étape pour comparer plusieurs fonds un par un "
                       "(via le paramètre source de rag_search).",
    },
    "read_file": {
        "function": read_file,
        "description": "Lit un fichier texte dont le nom est DÉJÀ connu (ex. une note écrite "
                       "à une étape précédente). Pour explorer les documents internes, "
                       "utiliser plutôt rag_search. Arguments : path (str).",
    },
    "write_file": {
        "function": write_file,
        "description": "Écrit un fichier dans le workspace : à réserver à la production du "
                       "livrable final. Ne reprendre que des valeurs DÉJÀ présentes dans la "
                       "mémoire de travail. INTERDICTION de calculer une valeur ici (somme, "
                       "écart, produit, pourcentage) : tout calcul doit avoir été fait AVANT "
                       "par calculator, et tu ne fais que recopier son résultat. "
                       "Arguments : path (str), content (str).",
    },
    "calculator": {
        "function": calculator,
        "description": "OBLIGATOIRE pour TOUT calcul arithmétique, même trivial (somme, "
                       "écart/soustraction, produit, division, pourcentage). Tu ne dois "
                       "JAMAIS calculer toi-même un nombre dans une réponse ou un fichier : "
                       "passe toujours par cet outil. Opère sur des nombres DÉJÀ connus "
                       "(présents dans la mémoire). NE PAS l'utiliser pour chercher une "
                       "information (pour ça : rag_search). Arguments : expression (str).",
    },
}


def tools_catalog() -> str:
    """Description des outils, injectée dans les prompts de sélection."""
    return "\n".join(f"- {name} : {spec['description']}" for name, spec in TOOLS.items())
