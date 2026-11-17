"""Persistence for the ingestion pipeline.

Idempotent by design: re-running ingestion over the same EUR-Lex page updates the
existing rows instead of duplicating them, so a failed run is safe to repeat.
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from ingest.embed import Embedder, to_pgvector
from ingest.models import Chunk, Source

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "init" / "01_schema.sql"


def connect(dsn: str | None = None) -> psycopg.Connection:
    dsn = dsn or os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:55432/eulaw")
    return psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5)


def apply_schema(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def upsert_document(conn: psycopg.Connection, source: Source, checksum: str) -> int:
    row = conn.execute(
        """
        INSERT INTO documents (slug, celex, title, lang, source_url, checksum)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (slug, lang) DO UPDATE
            SET celex = EXCLUDED.celex,
                title = EXCLUDED.title,
                source_url = EXCLUDED.source_url,
                checksum = EXCLUDED.checksum,
                fetched_at = now()
        RETURNING id
        """,
        (source.slug, source.celex, source.title, source.lang.lower(), source.public_url, checksum),
    ).fetchone()
    assert row is not None
    return int(row["id"])


def upsert_chunks(
    conn: psycopg.Connection,
    doc_id: int,
    chunks: list[Chunk],
    embedder: Embedder,
    embeddings: list[list[float]] | None = None,
) -> int:
    if not chunks:
        return 0
    if embeddings is None:
        embeddings = embedder.embed([c.content for c in chunks])
    if len(embeddings) != len(chunks):
        raise ValueError("embedding count does not match chunk count")

    rows = [
        (
            doc_id,
            c.lang,
            c.chapter,
            c.section,
            c.article,
            c.paragraph,
            c.is_recital,
            c.heading_path,
            c.content,
            c.n_chars,
            to_pgvector(vector),
            embedder.name,
        )
        for c, vector in zip(chunks, embeddings, strict=True)
    ]

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO chunks (
                doc_id, lang, chapter, section, article, paragraph, is_recital,
                heading_path, content, n_chars, embedding, embedding_model
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s)
            ON CONFLICT (doc_id, article, paragraph, lang, heading_path) DO UPDATE
                SET chapter = EXCLUDED.chapter,
                    section = EXCLUDED.section,
                    is_recital = EXCLUDED.is_recital,
                    content = EXCLUDED.content,
                    n_chars = EXCLUDED.n_chars,
                    embedding = EXCLUDED.embedding,
                    embedding_model = EXCLUDED.embedding_model
            """,
            rows,
        )
    conn.commit()
    return len(rows)


def stats(conn: psycopg.Connection) -> dict:
    documents = conn.execute(
        """
        SELECT d.slug, d.lang, count(c.id) AS chunks
        FROM documents d LEFT JOIN chunks c ON c.doc_id = d.id
        GROUP BY d.slug, d.lang ORDER BY d.slug, d.lang
        """
    ).fetchall()
    total = conn.execute("SELECT count(*) AS n FROM chunks").fetchone()
    return {"documents": documents, "chunks": int(total["n"]) if total else 0}
