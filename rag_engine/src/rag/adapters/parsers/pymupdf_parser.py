"""PyMuPDF-based PDF parser.

PyMuPDF (a.k.a. `fitz`) is fast, pure-Python, and good enough at text
extraction for born-digital course PDFs. For scanned PDFs we'd need OCR
(deferred to M8 per the roadmap).

The parser respects the `DocumentParser` Protocol from `rag.interfaces`:
    parse(path) -> tuple[list[ParentChunk], list[ChildChunk]]

Internally it does three things:
    1. extract text per page (PyMuPDF),
    2. split the page stream into sections (heuristics),
    3. chunk each section into parent + children (RecursiveCharacterTextSplitter).
"""

from __future__ import annotations

import re
from pathlib import Path

import pymupdf  # PyMuPDF >= 1.24 ships the `pymupdf` import alias

from rag.ingestion.chunker import ChunkingConfig, chunk_document
from rag.ingestion.sectioning import PageText, split_into_sections
from rag.interfaces.types import (
    ChildChunk,
    ClassificationLevel,
    ParentChunk,
)
from rag.utils.logging import get_logger

_log = get_logger(__name__)
_PARSER_VERSION = "pymupdf-1"


class PyMuPDFParser:
    """Baseline PDF parser. Fast, no external dependency beyond PyMuPDF."""

    def __init__(
        self,
        *,
        chunking: ChunkingConfig | None = None,
        language: str = "fr",
        classification: ClassificationLevel = ClassificationLevel.PUBLIC,
    ) -> None:
        self._chunking = chunking or ChunkingConfig()
        self._language = language
        self._classification = classification

    def parse(self, path: Path) -> tuple[list[ParentChunk], list[ChildChunk]]:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(path)

        pages = self._extract_pages(path)
        sections = split_into_sections(pages)
        parents, children = chunk_document(
            sections,
            source_file=path.name,
            config=self._chunking,
            language=self._language,
            classification=self._classification,
            parser_version=_PARSER_VERSION,
        )

        _log.info(
            "pdf parsed",
            source_file=path.name,
            pages=len(pages),
            sections=len(sections),
            parents=len(parents),
            children=len(children),
        )
        return parents, children

    @staticmethod
    def _extract_pages(path: Path) -> list[PageText]:
        """Return one `PageText` per PDF page (1-based numbering)."""
        out: list[PageText] = []
        # PyMuPDF ships partial stubs: `pymupdf.open` is flagged as untyped
        # under --strict even though it's perfectly safe. Ignore just here,
        # narrow code, with the rationale recorded for future maintainers.
        with pymupdf.open(path) as doc:  # type: ignore[no-untyped-call]
            for idx in range(doc.page_count):
                page = doc.load_page(idx)
                raw = page.get_text("text") or ""
                # Light normalisation: kill the most common PDF artefacts
                # (multiple blank lines, isolated form-feeds, hyphenation at EOL).
                cleaned = _clean_page_text(raw)
                if cleaned:
                    out.append(PageText(page=idx + 1, text=cleaned))
        return out


def _clean_page_text(text: str) -> str:
    """Minimal cleanup. Kept here (not in sectioning) so it's parser-specific."""
    # Soft hyphens left by some PDF exporters.
    text = text.replace("­", "")
    # End-of-line hyphenation: "exam-\nple" -> "example"
    text = _strip_eol_hyphenation(text)
    # Multiple blank lines down to two.
    out_lines: list[str] = []
    blank_run = 0
    for line in text.splitlines():
        if line.strip():
            blank_run = 0
            out_lines.append(line.rstrip())
        else:
            blank_run += 1
            if blank_run <= 1:
                out_lines.append("")
    return "\n".join(out_lines).strip()


def _strip_eol_hyphenation(text: str) -> str:
    """Join words split across line breaks with a trailing hyphen.

    Naive but safe: only when the next line starts with a lowercase letter.
    """
    return re.sub(r"-\n(?=[a-zà-ÿ])", "", text)
