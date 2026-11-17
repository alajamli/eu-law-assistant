"""Turn the Publications Office XHTML into structured legal units.

The markup that actually arrives (verified against the live Cellar endpoint, not
guessed from documentation) looks like this:

    <div class="eli-subdivision" id="art_5">
      <p class="oj-ti-art">Article 5</p>
      <div class="eli-title"><p class="oj-sti-art">Principles relating to processing</p></div>
      <div id="005.001">
        <p class="oj-normal">1. Personal data shall be:</p>
        <table>
          <tr><td><p class="oj-normal">(a)</p></td><td><p class="oj-normal">processed lawfully…</p></td></tr>
        </table>
      </div>
    </div>

Recitals use `id="rct_12"` and number themselves `(12)`. Note that the letter or
number marker sits in its **own** paragraph, in its own table cell — the naive
"one <p> = one paragraph" reading turns "(a)" into a chunk of its own, which is
one of the ways this pipeline could quietly produce useless retrieval.

Anything we cannot map structurally falls back to a text pass, because silently
losing articles would corrupt the eval set without failing any test.
"""

from __future__ import annotations

import re

from lxml import html as lxml_html

from ingest.models import Unit

ARTICLE_ID = re.compile(r"^art[_-](\d+[a-z]?)$", re.IGNORECASE)
RECITAL_ID = re.compile(r"^rct[_-](\d+)$", re.IGNORECASE)
HEADING_RE = re.compile(r"^[ \t]*(?:ARTICLE|Article)[ \t]+(\d+[a-z]?)[ \t]*$", re.MULTILINE)
CHAPTER_CLASSES = ("oj-ti-section-1", "oj-ti-section-2", "oj-ti-section-3")

# "1." at the start of a paragraph starts a numbered paragraph.
NUM_INLINE = re.compile(r"^(\d+)\.\s+")
# "(a)" or "(12)" alone in a paragraph is a marker for the next paragraph.
MARKER_ONLY = re.compile(r"^\((\d+|[a-z]{1,3})\)$")
# In the FR rendering, list items are inline: "… doivent être: a) … ; b) …".
# English puts them in separate table cells, so without this the French corpus
# ends up with article-sized chunks and the bilingual comparison is meaningless.
INLINE_SPLIT = re.compile(r"(?<=[;:])\s+(?=[a-z]\)\s)")
INLINE_MARKER = re.compile(r"^([a-z])\)\s*")
MIN_ITEM_CHARS = 25


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _text_of(el) -> str:
    return _clean(" ".join(t for t in el.itertext()))


def _class_tokens(el) -> set[str]:
    return set((el.get("class") or "").split())


def _expand_inline_items(label: str | None, text: str) -> list[tuple[str | None, str]]:
    """Split "intro: a) … ; b) …" into one unit per item, when it really is a list."""
    parts = INLINE_SPLIT.split(text)
    if len(parts) < 2:
        return [(label, text)]

    out: list[tuple[str | None, str]] = []
    for index, part in enumerate(parts):
        marker = INLINE_MARKER.match(part)
        if marker:
            out.append((marker.group(1), part[marker.end() :].strip()))
        else:
            out.append((label if index == 0 else None, part.strip()))
    return [(lab, body) for lab, body in out if body]


def _merge_fragments(items: list[list[str | None]]) -> list[list[str | None]]:
    """Reattach stray tail fragments such as "defence; or" to the previous item."""
    merged: list[list[str | None]] = []
    for label, text in items:
        if merged and len(text) < MIN_ITEM_CHARS and len(merged[-1][1]) >= MIN_ITEM_CHARS:
            merged[-1][1] = f"{merged[-1][1]} {text}".strip()
        else:
            merged.append([label, text])
    return merged


def _extract_paragraphs(container) -> list[tuple[str | None, str]]:
    """Return [(paragraph_label, text)], merging marker-only cells into their body."""
    items: list[list[str | None]] = []
    pending: str | None = None

    for p in container.iter("p"):
        if "oj-normal" not in _class_tokens(p):
            continue
        text = _text_of(p)
        if not text:
            continue

        marker = MARKER_ONLY.match(text)
        if marker:
            pending = marker.group(1)
            continue

        numbered = NUM_INLINE.match(text)
        if numbered:
            pending = None
            items.append([numbered.group(1), text[numbered.end() :].strip()])
            continue

        if pending is not None:
            items.append([pending, text])
            pending = None
        elif items:
            # Unnumbered continuation of the previous paragraph (common after a table).
            items[-1][1] = f"{items[-1][1]} {text}".strip()
        else:
            items.append([None, text])

    expanded: list[list[str | None]] = []
    for label, text in items:
        expanded.extend([list(pair) for pair in _expand_inline_items(label, text)])

    return [(label, text) for label, text in _merge_fragments(expanded) if text]


def parse_html(html: str | bytes, doc_title: str) -> list[Unit]:
    """Parse one legal document. Never raises on odd markup."""
    # The pipeline always stores UTF-8, and the Cellar payload declares it, but a
    # bare fragment does not: without an explicit encoding lxml falls back to
    # Latin-1 and every French accent becomes mojibake.
    parser = lxml_html.HTMLParser(encoding="utf-8")
    payload = html.encode("utf-8") if isinstance(html, str) else html
    doc = lxml_html.fromstring(payload, parser=parser)
    for bad in doc.xpath("//script | //style | //*[contains(@class,'oj-note-tag')]"):
        parent = bad.getparent()
        if parent is not None:
            parent.remove(bad)

    units: list[Unit] = []
    chapter: str | None = None
    section: str | None = None

    for el in doc.iter():
        if not isinstance(el.tag, str):
            continue
        classes = _class_tokens(el)

        if classes & set(CHAPTER_CLASSES):
            label = _text_of(el)
            if label:
                if "oj-ti-section-1" in classes:
                    chapter, section = label, None
                else:
                    section = label

        art_match = ARTICLE_ID.match(el.get("id") or "")
        rct_match = RECITAL_ID.match(el.get("id") or "")
        if not (art_match or rct_match):
            continue

        is_recital = bool(rct_match)
        identifier = (rct_match or art_match).group(1)
        paragraphs = _extract_paragraphs(el)
        if not paragraphs:
            continue

        titles = el.xpath('.//p[contains(@class,"oj-sti-art")]')
        title = _text_of(titles[0]) if titles else None

        for label, text in paragraphs:
            units.append(
                Unit(
                    article=identifier,
                    paragraph=None if is_recital else label,
                    text=text,
                    chapter=chapter,
                    section=section,
                    is_recital=is_recital,
                    title=title,
                )
            )

    return units or _fallback_split(doc.text_content())


def _fallback_split(plain_text: str) -> list[Unit]:
    """Last resort: split a text dump on 'Article N' headings.

    Used when the page has no ELI ids. Paragraph numbering is lost, so chunks are
    article-level.
    """
    matches = list(HEADING_RE.finditer(plain_text))
    if not matches:
        body = _clean(plain_text)
        return [Unit(article=None, paragraph=None, text=body)] if body else []

    units: list[Unit] = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(plain_text)
        body = _clean(plain_text[start:end])
        if body:
            units.append(Unit(article=match.group(1), paragraph=None, text=body))
    return units


def count_articles(units: list[Unit]) -> int:
    return len({u.article for u in units if u.article and not u.is_recital})
