"""The golden file is a contract: keep it loadable and schema-valid."""

import pytest

from evals.golden import GoldenQuestion, load_golden


def test_shipped_golden_file_loads():
    questions = load_golden(include_draft=True)
    assert len(questions) >= 5
    assert {q.type for q in questions} >= {"factual", "unanswerable"}


def test_drafts_are_excluded_by_default():
    shipped = load_golden(include_draft=True)
    verified = [q for q in shipped if q.status == "verified"]
    assert load_golden() == verified


def test_answerable_question_requires_gold_articles():
    with pytest.raises(ValueError, match="needs gold_articles"):
        GoldenQuestion(id="q", question="What is Article 5?", lang="en", type="factual")


def test_unanswerable_question_must_not_have_gold_articles():
    with pytest.raises(ValueError, match="must not list gold_articles"):
        GoldenQuestion(
            id="q", question="Anything about taxes?", lang="en", type="unanswerable", gold_articles=["gdpr:17"]
        )


def test_article_reference_must_be_slug_colon_article():
    with pytest.raises(ValueError, match="must look like"):
        GoldenQuestion(id="q", question="What is Article 5?", lang="en", type="factual", gold_articles=["5"])
