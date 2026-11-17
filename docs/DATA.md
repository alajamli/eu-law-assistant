# Data: source, licence, attribution

## Source

All legal text comes from **EUR-Lex**, the official database of EU law, published
by the Publications Office of the European Union.

| Document | CELEX | Source |
| --- | --- | --- |
| Artificial Intelligence Act — Regulation (EU) 2024/1689 | `32024R1689` | eur-lex.europa.eu |
| General Data Protection Regulation — Regulation (EU) 2016/679 | `32016R0679` | eur-lex.europa.eu |
| Data Act — Regulation (EU) 2023/2854 | `32023R2854` | eur-lex.europa.eu |

Both EN and FR versions are ingested. URLs are generated in
`ingest/sources.py`; the raw HTML is cached under `data/raw/` and is **not**
committed to the repository.

## Licence and attribution

Reuse of EUR-Lex content is covered by the European Commission's reuse policy
(Commission Decision 2011/833/EU on the reuse of Commission documents). Reuse is
permitted, including for commercial purposes, provided that:

1. the source is **acknowledged**;
2. the **original meaning is not distorted**;
3. the Commission's **official status is not implied** — the Commission is not
   responsible for the reuse, and no endorsement may be suggested.

This repository therefore states:

> Legal texts © European Union, reproduced from EUR-Lex. Reused under Commission
> Decision 2011/833/EU. This project is not an official EU source and is not
> endorsed by the European Union or the European Commission. It does not provide
> legal advice.

If you build something else from this corpus, keep that attribution.

## Caveats

- **Versions change.** The AI Act entered into force in 2024 and is being applied
  in stages; later amendments mean a text fetched today may not match a text
  fetched a year from now. `documents.checksum` records exactly what was indexed,
  and `documents.fetched_at` says when.
- **Only the regulation text is ingested**, not the accompanying guidance,
  implementing acts or national transposition.
- **Recitals are included** but flagged; they are not binding obligations.

## How the text is fetched

The obvious approach — `GET https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:…`
— no longer works for a plain HTTP client. EUR-Lex answers with HTTP 202 and an
AWS WAF JavaScript challenge, so a script receives a stub page (or nothing), and
a naive pipeline caches an empty corpus while reporting success.

This project therefore fetches from the **Publications Office Cellar** content
endpoint:

```
GET https://publications.europa.eu/resource/celex/{CELEX}
    Accept: application/xhtml+xml
    Accept-Language: eng | fra
```

It returns the same document with the same ELI markup (`art_5`, `rct_12`,
`eli-subdivision`) and no browser. Requesting `text/html` there returns 404 — the
`Accept` header is not optional.

`ingest/fetch.py` validates the payload (size, presence of ELI markup, minimum
number of subdivisions) and refuses to cache anything that fails, because a
firewall page is a 202, not an error.

