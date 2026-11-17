"""The three laws, in both languages.

Why the Publications Office and not eur-lex.europa.eu: the EUR-Lex web front end
sits behind an AWS WAF challenge and answers a plain HTTP client with a 202 and a
JavaScript stub. The Cellar content endpoint returns the same document with the
same ELI markup (`art_5`, `rct_12`, `eli-subdivision`), no browser required, and
is the officially recommended machine-readable route.

The language is negotiated with `Accept-Language`, so one URL serves EN and FR.
"""

from ingest.models import Source

_DOCS = [
    ("ai-act", "32024R1689", "EU Artificial Intelligence Act (Regulation (EU) 2024/1689)"),
    ("gdpr", "32016R0679", "General Data Protection Regulation (Regulation (EU) 2016/679)"),
    ("data-act", "32023R2854", "Data Act (Regulation (EU) 2023/2854)"),
]

CELLAR = "https://publications.europa.eu/resource/celex/{celex}"
EURLEX_PAGE = "https://eur-lex.europa.eu/legal-content/{lang}/TXT/?uri=CELEX:{celex}"

LANGS = ("en", "fr")


def sources() -> list[Source]:
    return [
        Source(
            slug=slug,
            celex=celex,
            title=title,
            lang=lang.upper(),
            url=CELLAR.format(celex=celex),
            public_url=EURLEX_PAGE.format(lang=lang.upper(), celex=celex),
        )
        for slug, celex, title in _DOCS
        for lang in LANGS
    ]


def by_slug(slug: str) -> list[Source]:
    matches = [s for s in sources() if s.slug == slug]
    if not matches:
        known = ", ".join(sorted({s.slug for s in sources()}))
        raise KeyError(f"unknown document '{slug}' (known: {known})")
    return matches
