"""Mini moteur RAG : indexe les fichiers de documents/ et cherche par similarité.

Utilise les embeddings Ollama si le modèle est disponible, sinon retombe sur
un score lexical simple (recouvrement de mots) pour rester fonctionnel.
"""
import re
from pathlib import Path

import numpy as np

from agent import llm

DOCUMENTS_DIR = Path(__file__).resolve().parent.parent / "documents"
CHUNK_SIZE = 800  # caractères
CHUNK_OVERLAP = 150
MIN_CHUNK = 30  # ignore les fragments trop courts (artefacts de découpage)


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
    """Index en mémoire : embeddings (ou mots-clés) des chunks des documents."""

    def __init__(self):
        self.chunks: list[dict] = []
        self.vectors: np.ndarray | None = None
        self.built = False

    def build(self):
        self.built = True
        self.chunks = []
        for path in sorted(DOCUMENTS_DIR.glob("**/*")):
            if path.suffix.lower() in {".txt", ".md"}:
                self.chunks.extend(_chunk(path.read_text(encoding="utf-8"), path.name))
        if not self.chunks:
            return
        try:
            vectors = np.array(llm.embed([c["text"] for c in self.chunks]))
            self.vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
        except Exception:
            self.vectors = None  # modèle d'embedding absent → mode lexical

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        if not self.built:
            self.build()
        if not self.chunks:
            return []
        if self.vectors is not None:
            q = np.array(llm.embed([query])[0])
            q = q / np.linalg.norm(q)
            scores = self.vectors @ q
        else:
            qw = _words(query)
            scores = np.array([
                len(qw & _words(c["text"])) / (len(qw) or 1) for c in self.chunks
            ])
        best = np.argsort(scores)[::-1][:top_k]
        return [{**self.chunks[i], "score": float(scores[i])} for i in best]


_index = RagIndex()


def rag_search(query: str, top_k: int = 3) -> str:
    """Recherche les passages les plus pertinents dans les documents indexés."""
    results = _index.search(query, top_k=max(int(top_k), 3))
    if not results:
        return "Aucun document trouvé dans le dossier documents/."
    return "\n\n".join(
        f"[{r['source']} — score {r['score']:.2f}]\n{r['text']}" for r in results
    )
