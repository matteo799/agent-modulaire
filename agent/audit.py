"""Piste d'audit — journal structuré et persistant d'un run de l'agent.

Complète les `print()` (lisibles à l'écran) et `workspace/notes.md` (état mental,
écrasé à chaque run) par une trace **auditable** : un fichier JSONL append-only
sous `logs/`, une ligne par événement, rattachée à un `run_id`.

Pourquoi (gouvernance) : sans journal persistant, on ne peut ni **tracer** une
décision de l'agent après coup, ni **investiguer** un incident (refus sécurité,
mauvais outil, dépassement de budget). Chaque événement porte l'horodatage, le
`run_id`, le type et sa charge utile — de quoi rejouer la trajectoire d'un run.

Principe de robustesse (comme le compteur de tokens) : **l'écriture du journal
ne doit JAMAIS casser un run**. Toute erreur d'I-O est avalée silencieusement —
l'observabilité est un service best-effort, pas un point de défaillance.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

# Journal versionné hors git (données de fonds + requêtes utilisateur). Voir .gitignore.
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
AUDIT_FILE = LOG_DIR / "audit.jsonl"

# Run courant (module-global) : `main` ouvre le run, les autres étages
# (`executor`, `security`…) émettent des événements sans avoir à se passer le
# run_id explicitement.
_current: dict = {"run_id": None, "start": None}

# Interrupteur : AGENT_AUDIT=0 désactive complètement le journal (tests, CI).
_ENABLED = os.environ.get("AGENT_AUDIT", "1") not in ("0", "false", "no")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _write(record: dict) -> None:
    """Ajoute une ligne JSON au journal — best-effort, ne lève jamais."""
    if not _ENABLED:
        return
    try:
        LOG_DIR.mkdir(exist_ok=True)
        with AUDIT_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:  # l'observabilité ne casse jamais un run
        pass


def start_run(query: str) -> str:
    """Ouvre un run auditable : génère un `run_id` et journalise la requête.

    Renvoie le `run_id` (utile pour l'afficher ou le corréler à un ticket)."""
    run_id = uuid.uuid4().hex[:12]
    _current["run_id"] = run_id
    _current["start"] = time.monotonic()
    _write({"ts": _now_iso(), "run_id": run_id, "event": "run_start", "query": query})
    return run_id


def event(name: str, **fields) -> None:
    """Journalise un événement quelconque du run courant (no-op hors run)."""
    if _current["run_id"] is None:
        return
    _write({"ts": _now_iso(), "run_id": _current["run_id"], "event": name, **fields})


def _preview(value, limit: int = 500) -> str:
    """Tronque un résultat pour le journal (on trace la trajectoire, pas le corpus)."""
    text = str(value).replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + f"… (+{len(text) - limit} car.)"


def step(index: int, description: str, tool: str, args: dict, result, ok: bool) -> None:
    """Journalise une étape de la boucle agentique (outil, args, aperçu du résultat)."""
    event(
        "step",
        index=index,
        step=description,
        tool=tool,
        args=args,
        ok=ok,
        result_preview=_preview(result),
    )


def end_run(status: str, **fields) -> None:
    """Clôt le run : statut (ok | refused | budget | llm_down…), usage, durée."""
    elapsed = None
    if _current["start"] is not None:
        elapsed = round(time.monotonic() - _current["start"], 2)
    event("run_end", status=status, elapsed_s=elapsed, **fields)
    _current["run_id"] = None
    _current["start"] = None
