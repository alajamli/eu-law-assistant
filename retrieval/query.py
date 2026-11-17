"""Query understanding: language and target-law detection.

Deliberately rule-based, not an LLM call: it runs on every request, must be free
and deterministic, and must not be able to fail. An LLM rewrite comes later
(Week 3) and is measured as an ablation, not assumed to help.
"""

from __future__ import annotations

import re

FR_MARKERS = {
    "le",
    "la",
    "les",
    "des",
    "est",
    "quel",
    "quelle",
    "quels",
    "quelles",
    "que",
    "qui",
    "dans",
    "pour",
    "avec",
    "sur",
    "pas",
    "une",
    "un",
    "du",
    "au",
    "aux",
    "et",
    "selon",
    "doit",
    "sont",
}
EN_MARKERS = {
    "the",
    "is",
    "are",
    "what",
    "which",
    "does",
    "do",
    "how",
    "and",
    "of",
    "in",
    "to",
    "a",
    "an",
    "must",
    "shall",
    "under",
}

LAW_PATTERNS: dict[str, list[str]] = {
    "ai-act": [
        r"\bai act\b",
        r"\bartificial intelligence act\b",
        r"\br[eè]glement (?:europ[eé]en )?sur l'intelligence artificielle\b",
        r"\bloi sur l'intelligence artificielle\b",
    ],
    "gdpr": [
        r"\bgdpr\b",
        r"\brgpd\b",
        r"\bgeneral data protection\b",
        r"\bprotection des donn[eé]es\b",
        r"2016/679",
    ],
    "data-act": [
        r"\bdata act\b",
        r"\bloi sur les donn[eé]es\b",
        r"2023/2854",
    ],
}

_LAW_REGEX = {slug: [re.compile(p, re.IGNORECASE) for p in pats] for slug, pats in LAW_PATTERNS.items()}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zà-ÿ']+", text.lower())


def detect_language(text: str) -> str:
    """Return 'fr' or 'en'. Ties and empty input fall back to 'en'."""
    tokens = _tokens(text)
    if not tokens:
        return "en"
    fr = sum(1 for t in tokens if t in FR_MARKERS)
    en = sum(1 for t in tokens if t in EN_MARKERS)
    return "fr" if fr > en else "en"


def detect_law(text: str) -> str | None:
    """Return a document slug, or None when the question is ambiguous."""
    for slug, patterns in _LAW_REGEX.items():
        if any(p.search(text) for p in patterns):
            return slug
    return None


def detect_article_reference(text: str) -> tuple[str, str] | None:
    """Find an explicit 'Article 5(1)(a)' / 'article 5' reference, if any."""
    match = re.search(r"art(?:icle)?\.?\s*(\d+[a-z]?)(?:\((\w+)\))?", text, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).lower(), (match.group(2) or "").lower()
