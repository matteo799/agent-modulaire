"""CLI for ingestion. Wired into `make ingest` and `python -m rag.ingestion.cli`.

We use Typer because we already depend on it and it gives us help text, typed
options, and `--help` for free. Stays a thin shell over `pipeline.ingest_directory`.

We use the modern `Annotated` pattern (PEP 593) instead of putting `typer.Option`
as a default value — that avoids ruff's B008 ("function call in argument
defaults") and is the form Typer recommends going forward.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from rag.config.settings import load_settings
from rag.ingestion.pipeline import ingest_directory
from rag.utils.logging import configure_logging, get_logger

app = typer.Typer(add_completion=False, help="Ingest PDFs into the configured stores.")

# Source unique des documents : `documents/` à la racine du dépôt, organisée par
# dataset (documents/finance, documents/droit). Le défaut pointe sur `finance`
# pour matcher la collection par défaut (`dataset_finance`) — une collection PAR
# dataset, jamais combinées. Pour ingérer le droit :
#   RAG__VECTOR_STORE__COLLECTION=dataset_droit python -m rag.ingestion.cli -s <repo>/documents/droit
# Chemin calculé depuis l'emplacement du package pour être indépendant du cwd.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_SRC = _REPO_ROOT / "documents" / "finance"


@app.command()
def main(
    src: Annotated[
        Path,
        typer.Option(
            "--src",
            "-s",
            help="Directory containing the PDFs to ingest (default: documents/finance).",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ] = _DEFAULT_SRC,
    pattern: Annotated[str, typer.Option("--pattern", help="Glob pattern.")] = "*.pdf",
    log_json: Annotated[bool, typer.Option("--log-json", help="Emit logs as JSON.")] = False,
    log_level: Annotated[str, typer.Option("--log-level", help="DEBUG / INFO / WARNING.")] = "INFO",
) -> None:
    configure_logging(level=log_level, json_output=log_json)
    log = get_logger("rag.ingestion.cli")

    settings = load_settings()
    log.info(
        "ingest cli starting",
        src=str(src),
        provider=settings.vector_store.provider,
        embedder=settings.embedder.model,
    )

    stats = ingest_directory(src, settings, pattern=pattern)
    log.info("ingest cli done", **stats)


if __name__ == "__main__":
    app()
