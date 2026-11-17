"""Query understanding tests: cheap, deterministic, and easy to get wrong."""

from retrieval.query import detect_article_reference, detect_language, detect_law


def test_detects_french():
    assert detect_language("Quelles sont les pratiques interdites par le règlement ?") == "fr"
    assert detect_language("Quel est le délai de notification d'une violation ?") == "fr"


def test_detects_english():
    assert detect_language("Which AI practices are prohibited in the EU?") == "en"
    assert detect_language("What is the maximum fine under the GDPR?") == "en"


def test_short_or_ambiguous_input_falls_back_to_english():
    assert detect_language("") == "en"
    assert detect_language("AI Act") == "en"


def test_detects_the_target_law_in_both_languages():
    assert detect_law("What does the AI Act say?") == "ai-act"
    assert detect_law("Quelles obligations selon le règlement sur l'intelligence artificielle ?") == "ai-act"
    assert detect_law("How long do I have to report a breach under the GDPR?") == "gdpr"
    assert detect_law("Que prévoit le RGPD ?") == "gdpr"


def test_returns_none_when_the_law_is_ambiguous():
    assert detect_law("What are my rights?") is None


def test_article_reference():
    assert detect_article_reference("Explain Article 5(1)(a)") == ("5", "1")
    assert detect_article_reference("what does art. 17 say") == ("17", "")
    assert detect_article_reference("what does the regulation say") is None
