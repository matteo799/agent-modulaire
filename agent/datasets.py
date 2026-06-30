"""Registre des datasets — UNE source de vérité.

Pour ajouter un dataset, il suffit d'un appel `register(Dataset(...))` ci-dessous :
tout ce qui consomme le registre (comptage `count_funds`, sélecteur Streamlit,
directive envoyée à l'agent…) se met à jour automatiquement. Aucun code générique
ne connaît le nom d'un dataset en particulier — il itère sur le registre.

Un `Dataset` ne décrit que LUI-MÊME (son périmètre, comment le compter), jamais
les autres : c'est ce qui permet d'en ajouter 1 ou 100 sans rien réécrire.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from agent.finance import amundi
from agent.rag_adapter import count_sources


@dataclass(frozen=True)
class Dataset:
    """Un dataset interrogeable par l'agent.

    key         : identifiant court et stable (ex. "amundi").
    label       : libellé affiché (Streamlit), ex. "Amundi (NAV / métriques)".
    description : ce que contient le dataset / pour quel type de question.
    unit        : ce qu'on compte (ex. "fonds", "documents").
    count       : fonction sans argument renvoyant le nombre d'éléments.
    """

    key: str
    label: str
    description: str
    unit: str
    count: Callable[[], int]

    def agent_directive(self) -> str:
        """Phrase déclarant à l'agent de QUEL dataset parle l'utilisateur.

        Générique : on déclare le périmètre, sans dicter quels outils employer
        (ce sont les descriptions des outils qui assurent le routage)."""
        return f"[La question porte sur le dataset « {self.label} » : {self.description}]"


_REGISTRY: dict[str, Dataset] = {}


def register(ds: Dataset) -> None:
    _REGISTRY[ds.key] = ds


def all_datasets() -> list[Dataset]:
    return list(_REGISTRY.values())


def find(query: str) -> Dataset | None:
    """Retrouve un dataset par sa clé ou son libellé (insensible à la casse)."""
    q = query.strip().lower()
    for ds in _REGISTRY.values():
        if q == ds.key or q in ds.label.lower() or q in ds.key:
            return ds
    return None


# ── Datasets déclarés ───────────────────────────────────────────────────────
# Pour en ajouter un : un seul `register(Dataset(...))`, et c'est tout.

register(
    Dataset(
        key="amundi",
        label="Amundi (NAV / métriques)",
        description="fonds structurés à NAV (faits exacts + calcul réel des métriques)",
        unit="fonds",
        count=amundi.count_funds,
    )
)

register(
    Dataset(
        key="finance",
        label="Finance (prospectus / KID)",
        description="prospectus/KID en texte libre indexés (recherche sémantique)",
        unit="documents",
        count=count_sources,
    )
)
