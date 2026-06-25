"""Schéma et chargeur du golden set d'évaluation (M6.1).

Le golden set est un YAML versionné dans `tests/rag_eval/golden/` qui
recense des questions, des réponses idéales, et les chunks sources qui
devaient être retrouvés. C'est notre référence pour :
- les métriques retrieval (recall@k, MRR sur `expected_chunk_ids`),
- les métriques génération (faithfulness vs `expected_answer`),
- la citation accuracy (les citations de la réponse pointent-elles vers
  `expected_source_files` ?).

Schéma : un fichier = une `GoldenSet` = liste de `GoldenItem`.
Pydantic valide à l'ouverture, donc une faute de frappe est attrapée tôt.

Pourquoi pas du JSON : YAML est plus lisible pour des annotateurs humains
(les Q/R contiennent des accents, des sauts de ligne, des guillemets).
Le seul prix est qu'on dépend de PyYAML, déjà dans les deps principales.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class GoldenItem(BaseModel):
    """Une entrée du golden set."""

    # Identifiant stable pour pouvoir suivre la régression d'une question
    # précise dans l'historique d'éval.
    id: str

    # Question utilisateur (langue d'origine, en pratique français).
    question: str

    # Réponse idéale, écrite par un humain. Sert de référence pour RAGAS et
    # autres métriques basées sur le ground-truth textuel.
    expected_answer: str

    # IDs des chunks (children ou parents) qui DOIVENT être retrouvés par
    # le retrieval pour qu'on considère la question correctement servie.
    # Au moins un suffit pour `hit@k`, l'ensemble compte pour recall@k.
    expected_chunk_ids: list[str] = Field(default_factory=list)

    # Fichiers sources autorisés pour les citations. La métrique
    # `citation_accuracy` vérifie que chaque citation pointe vers un de ces.
    expected_source_files: list[str] = Field(default_factory=list)

    # Tags libres pour filtrer / segmenter les rapports (ex. "acronyme",
    # "definition", "calcul"). Optionnel.
    tags: list[str] = Field(default_factory=list)


class GoldenSet(BaseModel):
    """Collection de `GoldenItem` + métadonnées de version."""

    version: str
    description: str = ""
    items: list[GoldenItem]

    def __len__(self) -> int:
        return len(self.items)


def load_golden_set(path: Path | str) -> GoldenSet:
    """Charge un YAML golden depuis `path` et valide via pydantic.

    Args:
        path: chemin vers le fichier YAML.

    Returns:
        Un `GoldenSet` validé.

    Raises:
        FileNotFoundError: si le fichier n'existe pas.
        pydantic.ValidationError: si le YAML ne respecte pas le schéma.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(p)
    with p.open("r", encoding="utf-8") as fp:
        raw = yaml.safe_load(fp) or {}
    return GoldenSet.model_validate(raw)
