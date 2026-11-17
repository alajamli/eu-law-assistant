"""Structure-aware chunking.

Rules (see docs/DECISIONS.md ADR-002):
  * never cut in the middle of a paragraph if the paragraph fits;
  * group consecutive paragraphs of the same article until `max_chars`;
  * always prepend the heading breadcrumb so a bare chunk still says where it is from;
  * recitals are kept but flagged, because they are not binding law.
"""

from __future__ import annotations

import re

from ingest.models import Chunk, Unit

MAX_CHARS = 1400
SENTENCE_END = re.compile(r"(?<=[.!?;])\s+")


def _split_long(text: str, max_chars: int) -> list[str]:
    """Split on sentence boundaries, then hard-wrap anything still too long."""
    if len(text) <= max_chars:
        return [text]

    pieces: list[str] = []
    current = ""
    for sentence in SENTENCE_END.split(text):
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            pieces.append(current)
        while len(sentence) > max_chars:
            pieces.append(sentence[:max_chars])
            sentence = sentence[max_chars:]
        current = sentence
    if current:
        pieces.append(current)
    return [p for p in pieces if p]


def _label(unit: Unit, part: int | None = None) -> str | None:
    if unit.is_recital or unit.paragraph is None:
        return unit.paragraph
    return f"{unit.paragraph} (cont. {part})" if part and part > 1 else unit.paragraph


def units_to_chunks(
    units: list[Unit],
    doc_slug: str,
    doc_title: str,
    lang: str,
    max_chars: int = MAX_CHARS,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    group: list[Unit] = []

    def flush() -> None:
        if not group:
            return
        first, last = group[0], group[-1]
        breadcrumb = first.breadcrumb(doc_title)
        body = "\n".join(u.text for u in group)
        paragraph = first.paragraph
        if len(group) > 1 and first.paragraph and last.paragraph and first.paragraph != last.paragraph:
            paragraph = f"{first.paragraph}-{last.paragraph}"
        content = f"{breadcrumb}\n\n{body}"
        chunks.append(
            Chunk(
                doc_slug=doc_slug,
                lang=lang,
                content=content,
                heading_path=breadcrumb,
                article=first.article,
                paragraph=paragraph,
                is_recital=first.is_recital,
                chapter=first.chapter,
                section=first.section,
            )
        )
        group.clear()

    for unit in units:
        same_article = (
            group
            and group[0].article == unit.article
            and group[0].is_recital == unit.is_recital
            and group[0].chapter == unit.chapter
        )
        projected = sum(len(u.text) for u in group) + len(unit.text)
        if same_article and projected <= max_chars:
            group.append(unit)
            continue

        # Start a new group.
        flush()
        group.append(unit)

        if len(unit.text) > max_chars:
            group.pop()
            breadcrumb = unit.breadcrumb(doc_title)
            for part, piece in enumerate(_split_long(unit.text, max_chars), start=1):
                label = _label(unit, part if len(piece) < len(unit.text) else None)
                chunks.append(
                    Chunk(
                        doc_slug=doc_slug,
                        lang=lang,
                        content=f"{breadcrumb}\n\n{piece}",
                        heading_path=breadcrumb,
                        article=unit.article,
                        paragraph=label,
                        is_recital=unit.is_recital,
                        chapter=unit.chapter,
                        section=unit.section,
                    )
                )

    flush()
    return chunks
