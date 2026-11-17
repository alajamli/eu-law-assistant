"""SQL retrieval: dense (pgvector) and lexical (Postgres full text).

The lexical side uses the `tsv` column filled by the `chunks_tsv_trigger` with a
config chosen per row (`english` / `french`). Without that, hybrid search would
silently be vector-only for French.
"""

from __future__ import annotations

import psycopg

from ingest.models import Hit

_SELECT = """
    c.id, c.article, c.paragraph, c.lang, c.heading_path, c.content, c.is_recital,
    d.slug, d.title, d.source_url
"""


def _filters(lang: str | None, law: str | None) -> tuple[list[str], list]:
    clauses, params = [], []
    if lang:
        clauses.append("c.lang = %s")
        params.append(lang)
    if law:
        clauses.append("d.slug = %s")
        params.append(law)
    return clauses, params


def _to_hit(row: dict, score: float) -> Hit:
    return Hit(
        chunk_id=int(row["id"]),
        doc=row["title"],
        article=row["article"],
        paragraph=row["paragraph"],
        lang=row["lang"],
        heading_path=row["heading_path"],
        content=row["content"],
        score=float(score),
        source_url=row["source_url"],
        is_recital=bool(row["is_recital"]),
        doc_slug=row["slug"],
    )


def vector_search(
    conn: psycopg.Connection,
    vector_literal: str,
    limit: int = 30,
    lang: str | None = None,
    law: str | None = None,
) -> list[Hit]:
    clauses, params = _filters(lang, law)
    where = " AND ".join(["c.embedding IS NOT NULL", *clauses])
    sql = f"""
        SELECT {_SELECT}, 1 - (c.embedding <=> %s::vector) AS score
        FROM chunks c
        JOIN documents d ON d.id = c.doc_id
        WHERE {where}
        ORDER BY c.embedding <=> %s::vector
        LIMIT %s
    """
    rows = conn.execute(sql, [vector_literal, *params, vector_literal, limit]).fetchall()
    return [_to_hit(row, row["score"]) for row in rows]


def keyword_search(
    conn: psycopg.Connection,
    query: str,
    limit: int = 30,
    lang: str | None = None,
    law: str | None = None,
) -> list[Hit]:
    config = "french" if lang == "fr" else "english"
    clauses, params = _filters(lang, law)
    where = " AND ".join(["c.tsv @@ q", *clauses])
    sql = f"""
        SELECT {_SELECT}, ts_rank_cd(c.tsv, q) AS score
        FROM chunks c
        JOIN documents d ON d.id = c.doc_id,
             websearch_to_tsquery(%s::regconfig, %s) AS q
        WHERE {where}
        ORDER BY score DESC
        LIMIT %s
    """
    try:
        rows = conn.execute(sql, [config, query, *params, limit]).fetchall()
    except psycopg.errors.SyntaxError:
        # A query made only of stop words produces an empty tsquery; not an error
        # worth propagating to the user.
        return []
    return [_to_hit(row, row["score"]) for row in rows]


def get_chunks(conn: psycopg.Connection, chunk_ids: list[int]) -> dict[int, Hit]:
    if not chunk_ids:
        return {}
    rows = conn.execute(
        f"SELECT {_SELECT} FROM chunks c JOIN documents d ON d.id = c.doc_id WHERE c.id = ANY(%s)",
        (chunk_ids,),
    ).fetchall()
    return {int(row["id"]): _to_hit(row, 0.0) for row in rows}


def get_article_text(
    conn: psycopg.Connection, doc_slug: str, article: str, lang: str
) -> list[dict]:
    """Parent-document expansion: the full article, ordered by paragraph."""
    rows = conn.execute(
        """
        SELECT c.article, c.paragraph, c.heading_path, c.content
        FROM chunks c
        JOIN documents d ON d.id = c.doc_id
        WHERE d.slug = %s AND c.article = %s AND c.lang = %s
        ORDER BY c.paragraph NULLS FIRST, c.id
        """,
        (doc_slug, article, lang),
    ).fetchall()
    return [dict(r) for r in rows]
