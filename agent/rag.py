"""Mini moteur RAG : indexe documents/ (.txt/.md/.pdf) et cherche par similarité.

Récupération hybride (embeddings Ollama + score lexical de mots-clés) avec un
seuil de pertinence pour ne rien renvoyer plutôt qu'halluciner hors-sujet.
L'index est persisté sur disque pour éviter de ré-embedder à chaque lancement.
Si le modèle d'embedding est absent, dégradation gracieuse en mode lexical seul.
"""
import math
import pickle
import re
from collections import Counter
from pathlib import Path

import numpy as np

from agent import llm

DOCUMENTS_DIR = Path(__file__).resolve().parent.parent / "documents"
CACHE_PATH = Path(__file__).resolve().parent.parent / "workspace" / ".rag_cache.pkl"
CHUNK_SIZE = 800  # caractères
CHUNK_OVERLAP = 150
MIN_CHUNK = 30  # ignore les fragments trop courts (artefacts de découpage)
SUPPORTED = {".txt", ".md", ".pdf"}

# Récupération hybride : score de classement = DENSE_WEIGHT * cosinus +
# (1-DENSE_WEIGHT) * lexical. Le lexical est pondéré par IDF (rareté du mot) :
# les mots absents du corpus (TVA, prêt…) pèsent lourd et les mots omniprésents
# (taux, règles…) presque rien — c'est ce qui distingue le hors-sujet.
DENSE_WEIGHT = 0.6
# Garde-fou anti-hallucination : si AUCUN passage n'atteint ce score lexical IDF,
# la requête est jugée hors-sujet et rag_search ne renvoie rien. Le cosinus de
# nomic-embed est trop « plat » (~0,9 partout) pour servir de seuil ; le lexical
# IDF, lui, sépare nettement l'in-domain du hors-sujet.
LEXICAL_GATE = 0.46


def _signature() -> list:
    """Empreinte du corpus (nom, taille, mtime) pour invalider le cache."""
    return sorted(
        (p.name, p.stat().st_size, p.stat().st_mtime_ns)
        for p in DOCUMENTS_DIR.glob("**/*")
        if p.suffix.lower() in SUPPORTED
    )


def _read_document(path: Path) -> str:
    """Texte d'un document. .txt/.md lus directement ; .pdf extrait via pypdf.

    Si pypdf est absent ou le PDF illisible, renvoie une chaîne vide : le
    document est alors ignoré (dégradation gracieuse, comme pour les embeddings)."""
    if path.suffix.lower() == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception:
            return ""
    return path.read_text(encoding="utf-8")


def _split_sections(text: str) -> list[str]:
    """Découpe le document sur les titres markdown ; chaque section conserve
    son titre, ce qui garde des chunks sémantiquement cohérents."""
    sections, current = [], []
    for line in text.splitlines():
        if line.startswith("#") and current:
            sections.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current).strip())
    return [s for s in sections if s]


def _chunk(text: str, source: str) -> list[dict]:
    """Un chunk par section ; les sections trop longues sont redécoupées en
    fenêtres glissantes. Évite les fragments minuscules que produisait
    l'ancien découpage aveugle par tranches de caractères."""
    chunks = []
    step = CHUNK_SIZE - CHUNK_OVERLAP
    for section in _split_sections(text):
        if len(section) <= CHUNK_SIZE:
            pieces = [section]
        else:
            pieces = [section[i:i + CHUNK_SIZE].strip()
                      for i in range(0, len(section), step)]
        for piece in pieces:
            if len(piece) >= MIN_CHUNK:
                chunks.append({"source": source, "text": piece})
    return chunks


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"\w+", text.lower()) if len(w) > 2}


class RagIndex:
    """Index : chunks + embeddings + ensembles de mots, persisté sur disque."""

    def __init__(self):
        self.chunks: list[dict] = []
        self.vectors: np.ndarray | None = None
        self.word_sets: list[set] = []  # mots de chaque chunk (score lexical)
        self.df: Counter = Counter()    # nb de chunks contenant chaque mot
        self.built = False

    def build(self):
        self.built = True
        sig = _signature()
        if self._load_cache(sig):
            return
        self.chunks = []
        for path in sorted(DOCUMENTS_DIR.glob("**/*")):
            if path.suffix.lower() in SUPPORTED:
                text = _read_document(path)
                if text.strip():
                    self.chunks.extend(_chunk(text, path.name))
        self.word_sets = [_words(c["text"]) for c in self.chunks]
        self.df = Counter(w for ws in self.word_sets for w in ws)
        if not self.chunks:
            return
        try:
            vectors = np.array(llm.embed([c["text"] for c in self.chunks]))
            self.vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
        except Exception:
            self.vectors = None  # modèle d'embedding absent → mode lexical
        self._save_cache(sig)

    def _load_cache(self, sig) -> bool:
        try:
            with open(CACHE_PATH, "rb") as f:
                data = pickle.load(f)
            if data.get("signature") != sig:
                return False
            self.chunks = data["chunks"]
            self.vectors = data["vectors"]
            self.word_sets = data["word_sets"]
            self.df = data["df"]
            return True
        except Exception:
            return False

    def _save_cache(self, sig):
        try:
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_PATH, "wb") as f:
                pickle.dump({"signature": sig, "chunks": self.chunks,
                             "vectors": self.vectors, "word_sets": self.word_sets,
                             "df": self.df}, f)
        except Exception:
            pass  # cache best-effort : un échec d'écriture ne casse rien

    def _lexical(self, qw: set, idx: list) -> np.ndarray:
        """Recouvrement de mots pondéré par IDF, dans [0, 1]. Un mot rare (ou
        absent du corpus) pèse beaucoup ; un mot omniprésent presque rien."""
        n = len(self.chunks)
        weights = {w: math.log((n + 1) / (self.df.get(w, 0) + 1)) + 1.0 for w in qw}
        total = sum(weights.values()) or 1.0
        return np.array([
            sum(weights[w] for w in qw if w in self.word_sets[i]) / total
            for i in idx
        ])

    def search(self, query: str, top_k: int = 3, source: str = "") -> list[dict]:
        if not self.built:
            self.build()
        if not self.chunks:
            return []
        # Filtre éventuel par document source (sous-chaîne, ex. un ISIN).
        idx = [i for i, c in enumerate(self.chunks)
               if not source or source.lower() in c["source"].lower()]
        if not idx:
            return []
        lexical = self._lexical(_words(query), idx)
        # Garde-fou hors-sujet : si rien n'atteint le seuil lexical IDF, on ne
        # renvoie rien (le cosinus seul ne sait pas dire « hors-sujet »).
        if lexical.max(initial=0.0) < LEXICAL_GATE:
            return []
        if self.vectors is not None:
            q = np.array(llm.embed([query])[0])
            q = q / np.linalg.norm(q)
            dense = np.clip(self.vectors[idx] @ q, 0, 1)
            scores = DENSE_WEIGHT * dense + (1 - DENSE_WEIGHT) * lexical
        else:
            scores = lexical
        order = np.argsort(scores)[::-1][:top_k]
        return [{**self.chunks[idx[o]], "score": float(scores[o])} for o in order]

    def sources(self) -> list[str]:
        if not self.built:
            self.build()
        return sorted({c["source"] for c in self.chunks})


_index = RagIndex()


def rag_search(query: str, top_k: int = 3, source: str = "") -> str:
    """Recherche les passages pertinents. `source` (optionnel) restreint à un
    document (ex. un ISIN). Renvoie un message clair si rien n'est pertinent."""
    results = _index.search(query, top_k=max(int(top_k), 3), source=source)
    if not results:
        return ("Aucun passage pertinent trouvé dans les documents pour cette "
                "recherche : le sujet ne semble pas couvert par les documents "
                "disponibles.")
    return "\n\n".join(
        f"[{r['source']} — score {r['score']:.2f}]\n{r['text']}" for r in results
    )


def list_sources() -> str:
    """Liste les documents (fonds) indexés dans documents/."""
    srcs = _index.sources()
    if not srcs:
        return "Aucun document dans le dossier documents/."
    return "Documents disponibles :\n" + "\n".join(f"- {s}" for s in srcs)
