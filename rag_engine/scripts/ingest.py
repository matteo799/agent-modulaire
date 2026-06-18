#!/usr/bin/env python3
"""Thin entry point so `python scripts/ingest.py --help` works without
remembering the module path (équivalent à `python -m rag.ingestion.cli`).
"""

from __future__ import annotations

from rag.ingestion.cli import app

if __name__ == "__main__":
    app()
