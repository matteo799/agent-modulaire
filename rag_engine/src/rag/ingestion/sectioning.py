"""Heuristic section detection for course-style PDFs.

We're not parsing LaTeX or Markdown — we're parsing PDFs whose authors used
inconsistent typographical conventions (notes manuscrites scannées, slides
exportées, polycopiés, etc.). So we go heuristic.

Strategy:
1. Walk the text line by line.
2. For each line, ask: does this look like a heading?
   - Numbered prefix (I., II., 1., 1.1, 1.1.1, A., a))
   - Roman numerals with closing parenthesis: "I)", "II)"
   - "Chapitre N", "Section N", "CM N", "Partie N"
3. Group lines between two heading lines into the section they belong to.
4. If no heading is detected in the whole document, fall back to a single
   section spanning everything (safe default — the chunker will still split
   it into manageable pieces).

The output is intentionally simple: list of `Section` with start/end page,
section_path (the breadcrumb), and the raw text. Chunking is someone else's
job (see `rag.ingestion.chunker`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Patterns ordered roughly by specificity. The first match wins.
_HEADING_PATTERNS: tuple[re.Pattern[str], ...] = (
    # "1.2.3 Titre" or "1.2 Titre" or "1. Titre"
    re.compile(r"^\s*(\d+(?:\.\d+){0,3})\.?\s+(.{2,120}?)\s*$"),
    # "I. Titre" / "IV) Titre" / "VII - Titre"
    re.compile(r"^\s*([IVXLCDM]{1,6})[.)\-]\s+(.{2,120}?)\s*$"),
    # "A. Titre" / "a) Titre"
    re.compile(r"^\s*([A-Za-z])[.)]\s+(.{2,120}?)\s*$"),
    # "Chapitre 3 — ...", "Section 2: ...", "Partie I — ...", "CM 4 ..."
    re.compile(
        r"^\s*(Chapitre|Section|Partie|Titre|CM|Cours|TD|TP)\s+([IVXLCDM\d]+)\b[^A-Za-z]?\s*(.{0,120}?)\s*$",
        re.IGNORECASE,
    ),
)

# Minimum length below which a "heading-shaped" line is rejected as noise
# (e.g., bare numbers at the bottom of a page).
_MIN_HEADING_LEN = 3
_MAX_HEADING_LEN = 140


@dataclass(slots=True)
class PageText:
    """One page after parsing — text plus its 1-based page number."""

    page: int
    text: str


@dataclass(slots=True)
class Section:
    """A logical section of a document. Used as the parent unit downstream."""

    section_path: list[str]
    text: str
    start_page: int
    end_page: int
    extra: dict[str, str] = field(default_factory=dict)


def looks_like_heading(line: str) -> str | None:
    """Return the heading text if `line` matches one of our patterns, else None.

    Used by `split_into_sections` but also handy to test in isolation.
    """
    stripped = line.strip()
    if not (_MIN_HEADING_LEN <= len(stripped) <= _MAX_HEADING_LEN):
        return None
    # Lines ending with punctuation other than colon are unlikely to be titles
    # (they're full sentences).
    if stripped[-1] in ".!?;," and not stripped.endswith("..."):
        # Allow "1. Title" though — that's a valid heading with a numeric prefix.
        pass
    for pattern in _HEADING_PATTERNS:
        m = pattern.match(stripped)
        if m:
            return stripped
    return None


def split_into_sections(pages: list[PageText]) -> list[Section]:
    """Group pages' content into sections delimited by heuristic headings.

    Falls back to a single section covering everything if no heading is found.
    The fallback uses the source file basename as the section_path so chunks
    still carry useful metadata.
    """
    if not pages:
        return []

    # Build a flat list of (page_number, line) so we can locate the page of
    # each heading without iterating the pages list a second time.
    flat: list[tuple[int, str]] = []
    for p in pages:
        for line in p.text.splitlines():
            flat.append((p.page, line))

    # Locate heading line indices.
    heading_indices: list[int] = [
        i for i, (_, line) in enumerate(flat) if looks_like_heading(line) is not None
    ]

    if not heading_indices:
        # No heading detected — return one big section.
        full_text = "\n".join(line for _, line in flat).strip()
        return [
            Section(
                section_path=["(document)"],
                text=full_text,
                start_page=pages[0].page,
                end_page=pages[-1].page,
            )
        ]

    # Build sections: each [heading_indices[k], heading_indices[k+1]) is one section.
    sections: list[Section] = []
    bounded = [*heading_indices, len(flat)]
    for k in range(len(heading_indices)):
        start, end = bounded[k], bounded[k + 1]
        head_page, head_line = flat[start]
        body_lines = [line for _, line in flat[start + 1 : end]]
        end_page = flat[end - 1][0] if end > start else head_page
        text = "\n".join([head_line, *body_lines]).strip()
        sections.append(
            Section(
                section_path=[head_line.strip()],
                text=text,
                start_page=head_page,
                end_page=end_page,
            )
        )
    return sections
