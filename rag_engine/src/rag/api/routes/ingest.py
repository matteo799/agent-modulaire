"""Router `/ingest` (M5.1) — upload PDF → pipeline d'ingestion synchrone.

Synchrone parce que le POC tient sur des corpus de cours (~1-50 MB par PDF).
Si la volumétrie justifie une file de travail (Celery / RQ), ce sera une PR
distincte en M5+ ; l'API gardera la même signature.

Le fichier uploadé est :
1. validé sommairement (extension `.pdf`, taille raisonnable),
2. sauvegardé en `tmp_path / uploaded.pdf`,
3. passé au pipeline d'ingestion qui lit, chunk, embed et upsert.

Pas de chiffrement au repos sur le disque temporaire : on est en POC en
domaine sensible mais sur des cours « publics ». Quand on passera sur du
restreint/confidentiel, il faudra une PR dédiée pour wiper le tmp et chiffrer.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from rag.adapters.doc_stores.sqlite_store import SQLiteDocumentStore
from rag.adapters.parsers.pymupdf_parser import PyMuPDFParser
from rag.api.deps import get_settings
from rag.config.factory import build_embedder, build_vector_store
from rag.config.settings import Settings
from rag.ingestion.pipeline import ingest_pdf
from rag.utils.logging import get_logger

_log = get_logger(__name__)

# Limite haute pour la taille d'upload — protège contre une PR
# qui pousserait un GB par erreur. Configurable plus tard si besoin.
_MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB

router = APIRouter(tags=["ingest"])


class IngestResponse(BaseModel):
    """Stats renvoyées après ingestion."""

    filename: str
    parents: int
    children: int
    vector_count: int
    doc_count: int


# Type alias pour la fonction d'ingestion injectable. Permet aux tests de
# remplacer toute la logique par un stub via `dependency_overrides`.
IngestFn = Callable[[Path, str], dict[str, int]]


def _build_ingest_callable(settings: Settings) -> IngestFn:
    """Construit la fonction d'ingestion en câblant les adapters depuis settings.

    Sortie : `(pdf_path, original_filename) -> stats`.

    On garde le `original_filename` séparé du chemin réel : le pipeline
    persiste le nom de fichier d'origine dans les metadata, pas le chemin
    temporaire serveur.
    """
    parser = PyMuPDFParser()
    doc_store = SQLiteDocumentStore(db_path=settings.data_dir / "parents.sqlite")
    # Le vector store est résolu par la factory (Qdrant). Le pipeline est
    # provider-agnostique : il ne dépend que du protocole VectorStore.
    vstore_obj = build_vector_store(settings)
    embedder = build_embedder(settings)

    def _ingest(pdf_path: Path, original_filename: str) -> dict[str, int]:
        # On renomme localement pour que les metadata enregistrent le bon
        # nom (pas `uploaded.pdf` mais le nom réel du fichier client).
        renamed = pdf_path.parent / original_filename
        if renamed != pdf_path:
            shutil.copy2(pdf_path, renamed)
        return ingest_pdf(
            renamed,
            parser=parser,
            doc_store=doc_store,
            vector_store=vstore_obj,
            embedder_embed=embedder.embed,
        )

    return _ingest


def get_ingest_fn(settings: Settings = Depends(get_settings)) -> IngestFn:
    """Dépendance injectée — override-able en test."""
    return _build_ingest_callable(settings)


@router.post("/ingest", response_model=IngestResponse)
async def ingest_endpoint(
    file: UploadFile = File(..., description="PDF à ingérer"),
    ingest_fn: IngestFn = Depends(get_ingest_fn),
) -> IngestResponse:
    """Upload synchrone d'un PDF + ingestion immédiate.

    Validation :
    - extension `.pdf` requise,
    - taille ≤ 100 MB.
    """
    filename = file.filename or "uploaded.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="seuls les fichiers .pdf sont acceptés")

    # On écrit dans un répertoire temporaire dédié, supprimé en fin de bloc.
    with tempfile.TemporaryDirectory(prefix="rag-ingest-") as tmp:
        tmp_dir = Path(tmp)
        tmp_path = tmp_dir / "uploaded.pdf"
        total = 0
        with tmp_path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > _MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"fichier trop gros (> {_MAX_UPLOAD_BYTES} octets)",
                    )
                out.write(chunk)
        _log.info("ingest upload received", filename=filename, bytes=total)
        stats = ingest_fn(tmp_path, filename)

    return IngestResponse(
        filename=filename,
        parents=stats.get("parents", 0),
        children=stats.get("children", 0),
        vector_count=stats.get("vector_count", 0),
        doc_count=stats.get("doc_count", 0),
    )
