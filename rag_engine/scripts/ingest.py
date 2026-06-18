#!/usr/bin/env python3
"""Thin entry point so `python scripts/ingest.py --help` and the Makefile cible
`make ingest` both work without remembering the module path.
"""

from __future__ import annotations

from rag.ingestion.cli import app

if __name__ == "__main__":
    app()
