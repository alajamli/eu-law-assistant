"""Chunking tests: breadcrumb, grouping, and the long-article split."""

from ingest.chunk import units_to_chunks
from ingest.models import Unit

TITLE = "GDPR"
SLUG = "gdpr"


def _units(*texts: str) -> list[Unit]:
    return [
        Unit(article="17", paragraph=str(i + 1), text=text, chapter="CHAPTER III")
        for i, text in enumerate(texts)
    ]


def test_breadcrumb_is_prepended():
    chunks = units_to_chunks(_units("Right to erasure."), SLUG, TITLE, "en")
    assert len(chunks) == 1
    assert chunks[0].content.startswith("GDPR > CHAPTER III > Article 17(1)")
    assert chunks[0].paragraph == "1"


def test_short_paragraphs_of_the_same_article_are_grouped():
    chunks = units_to_chunks(_units("One.", "Two.", "Three."), SLUG, TITLE, "en")
    assert len(chunks) == 1
    assert chunks[0].paragraph == "1-3"
    assert chunks[0].content.count("Article 17") == 1


def test_group_breaks_when_the_budget_is_exceeded():
    chunks = units_to_chunks(_units("a" * 300, "b" * 300, "c" * 300), SLUG, TITLE, "en", max_chars=650)
    assert len(chunks) == 2
    assert all(len(c.content) <= 650 + len(c.heading_path) + 2 for c in chunks)


def test_long_paragraph_is_split_on_sentences_and_labelled_cont():
    text = " ".join(f"Sentence number {i} about erasure rules." for i in range(40))
    chunks = units_to_chunks(_units(text), SLUG, TITLE, "en", max_chars=400)
    assert len(chunks) > 1
    assert chunks[0].paragraph == "1"
    assert chunks[1].paragraph == "1 (cont. 2)"
    assert all(len(c.content) <= 400 + len(c.heading_path) + 2 for c in chunks)


def test_recital_is_marked_in_the_breadcrumb():
    unit = Unit(article="12", paragraph=None, text="This Regulation applies.", is_recital=True)
    chunk = units_to_chunks([unit], SLUG, TITLE, "en")[0]
    assert "Recital 12" in chunk.heading_path
    assert chunk.is_recital is True
