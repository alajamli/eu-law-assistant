"""Shared domain types for ingestion and retrieval."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Source:
    """One law, in one language.

    `url` is the Publications Office Cellar endpoint, which serves the document
    with its ELI markup and is not behind the EUR-Lex web application firewall.
    `public_url` is the human-readable page used in citations.
    """

    slug: str
    celex: str
    title: str
    lang: str
    url: str
    public_url: str


@dataclass
class Unit:
    """A parsed legal unit before chunking (one article paragraph, or one recital)."""

    article: str | None
    paragraph: str | None
    text: str
    chapter: str | None = None
    section: str | None = None
    is_recital: bool = False
    title: str | None = None

    def breadcrumb(self, doc_title: str) -> str:
        parts = [doc_title]
        if self.chapter:
            parts.append(self.chapter)
        if self.section:
            parts.append(self.section)
        if self.is_recital:
            parts.append(f"Recital {self.article}")
        elif self.article:
            label = f"Article {self.article}"
            if self.paragraph:
                label += f"({self.paragraph})"
            if self.title:
                label += f" — {self.title}"
            parts.append(label)
        return " > ".join(parts)


@dataclass
class Chunk:
    """A retrievable unit: breadcrumb-prefixed text plus the metadata we cite."""

    doc_slug: str
    lang: str
    content: str
    heading_path: str
    article: str | None
    paragraph: str | None
    is_recital: bool = False
    chapter: str | None = None
    section: str | None = None

    @property
    def n_chars(self) -> int:
        return len(self.content)


@dataclass
class Hit:
    """A retrieval result returned by the pipeline and serialised by the API."""

    chunk_id: int
    doc: str
    article: str | None
    paragraph: str | None
    lang: str
    heading_path: str
    content: str
    score: float
    source_url: str | None = None
    is_recital: bool = False
    doc_slug: str = ""
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "doc": self.doc,
            "article": self.article,
            "paragraph": self.paragraph,
            "lang": self.lang,
            "heading_path": self.heading_path,
            "content": self.content,
            "score": self.score,
            "source_url": self.source_url,
        }
