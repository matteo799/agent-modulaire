"""Router `/healthz` + `/readyz` (M5.4).

Convention Kubernetes / probes :
- **healthz** : « le process est vivant ». Réponse triviale, jamais bloquante.
  Si /healthz échoue, le process est tué et redémarré.
- **readyz**  : « le process est prêt à servir du trafic ». Vérifie les
  dépendances externes (Qdrant, Ollama). Si /readyz échoue, le load balancer
  cesse d'envoyer du trafic mais ne tue pas le process.

`/readyz` ne plante PAS si les deps sont absentes, il renvoie 503. Ça permet
de démarrer l'app avant les services et d'attendre qu'ils répondent.
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from rag.api.deps import get_settings
from rag.config.settings import Settings
from rag.utils.logging import get_logger

_log = get_logger(__name__)

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    checks: dict[str, str] = {}


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    """Process vivant. Réponse triviale, pas d'I/O."""
    return HealthResponse(status="ok")


def _check_ollama(base_url: str) -> tuple[bool, str]:
    """Ping Ollama via /api/tags (endpoint trivial qui liste les modèles)."""
    try:
        resp = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=2.0)
        if resp.status_code == 200:
            return True, "ok"
        return False, f"http {resp.status_code}"
    except httpx.HTTPError as exc:
        return False, f"unreachable: {type(exc).__name__}"


def _check_qdrant_local(qdrant_dir: str) -> tuple[bool, str]:
    """Pour Qdrant local embarqué, on vérifie juste l'existence du dossier.

    Une vérif plus poussée (count() sur la collection) ouvrirait un client
    Qdrant, ce qui ralentirait le readyz (et verrouillerait le store local).
    On garde léger.
    """
    from pathlib import Path

    p = Path(qdrant_dir)
    if p.is_dir():
        return True, "ok"
    return False, f"qdrant local dir absent: {p}"


@router.get("/readyz")
def readyz(settings: Settings = Depends(get_settings)) -> Any:
    """Vérifie les deps. Renvoie 200 si tout est ok, 503 sinon.

    On utilise `JSONResponse(status_code=503)` au lieu de `HTTPException`
    parce qu'on veut renvoyer le détail des checks dans le body, même en
    cas d'échec.
    """
    checks: dict[str, str] = {}

    # Ollama : configuré uniquement si provider == "ollama".
    if settings.llm.provider == "ollama":
        ok, detail = _check_ollama(settings.llm.ollama.base_url)
        checks["ollama"] = detail
    else:
        checks["ollama"] = "skipped (provider != ollama)"
        ok = True

    # Vector store : Qdrant. En mode local embarqué (url vide), on vérifie le
    # dossier sur disque ; en mode serveur, on ne probe pas ici (laisse au client).
    if not settings.vector_store.qdrant.url.strip():
        qd_ok, qd_detail = _check_qdrant_local(str(settings.data_dir / "qdrant"))
        checks["qdrant"] = qd_detail
        ok = ok and qd_ok
    else:
        checks["qdrant"] = f"server configured: {settings.vector_store.qdrant.url}"

    body = HealthResponse(status="ok" if ok else "not_ready", checks=checks).model_dump()
    if not ok:
        _log.warning("readyz failed", checks=checks)
        return JSONResponse(status_code=503, content=body)
    return JSONResponse(status_code=200, content=body)
