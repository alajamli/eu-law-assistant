"""The corpus registry must stay small, explicit and bilingual."""

from ingest import sources


def test_six_sources_three_laws_two_languages():
    all_sources = sources.sources()
    assert len(all_sources) == 6
    assert {s.slug for s in all_sources} == {"ai-act", "gdpr", "data-act"}
    assert {s.lang for s in all_sources} == {"EN", "FR"}


def test_documents_are_fetched_from_the_publications_office():
    for source in sources.sources():
        assert source.url.startswith("https://publications.europa.eu/resource/celex/")
        assert source.celex in source.url


def test_citations_link_to_the_human_eurlex_page():
    for source in sources.sources():
        assert source.public_url.startswith("https://eur-lex.europa.eu/")
        assert source.celex in source.public_url
        assert f"/{source.lang}/" in source.public_url


def test_by_slug_returns_both_languages():
    assert [s.lang for s in sources.by_slug("gdpr")] == ["EN", "FR"]


def test_unknown_slug_is_explicit():
    try:
        sources.by_slug("dma")
    except KeyError as exc:
        assert "ai-act" in str(exc)
    else:
        raise AssertionError("expected KeyError")
