"""The retrieval pipeline: dense + lexical -> RRF -> rerank.

Each stage is a separate module so Week 3's ablation table can turn them on and
off independently (`Retriever(use_hybrid=False, use_rerank=False)` is exactly
the v0 baseline).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from api.config import Settings, get_settings
from ingest.embed import Embedder, get_embedder, to_pgvector
from ingest.models import Hit
from retrieval import search
from retrieval.fusion import reciprocal_rank_fusion
from retrieval.query import detect_language, detect_law
from retrieval.rerank import NoopReranker, Reranker, get_reranker


class Retriever:
    def __init__(
        self,
        conn: psycopg.Connection | None = None,
        embedder: Embedder | None = None,
        reranker: Reranker | None = None,
        settings: Settings | None = None,
        *,
        use_hybrid: bool = True,
        use_rerank: bool | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._conn = conn
        self._embedder = embedder
        self.use_hybrid = use_hybrid
        if use_rerank is None:
            use_rerank = self.settings.rerank_enabled
        self._reranker = reranker
        self._use_rerank = use_rerank
        self._owns_reranker = reranker is None

    @property
    def embedder(self) -> Embedder:
        if self._embedder is None:
            self._embedder = get_embedder(
                self.settings.embedding_backend, self.settings.embedding_model, self.settings.embedding_dim
            )
        return self._embedder

    @property
    def reranker(self) -> Reranker:
        if self._reranker is None:
            if self._use_rerank:
                self._reranker = get_reranker(True, self.settings.reranker_model)
            else:
                self._reranker = NoopReranker()
        return self._reranker

    @contextmanager
    def _connection(self) -> Iterator[psycopg.Connection]:
        if self._conn is not None:
            yield self._conn
            return
        from api.db import get_pool

        with get_pool().connection() as conn:
            yield conn

    def search(
        self,
        question: str,
        lang: str = "auto",
        top_n: int | None = None,
        law: str | None = None,
    ) -> list[Hit]:
        resolved_lang = detect_language(question) if lang == "auto" else lang
        resolved_law = detect_law(question) if law is None else law
        top_n = top_n or self.settings.rerank_top_n
        depth = max(self.settings.retrieve_top_k, top_n)

        vector = self.embedder.embed([question])[0]
        with self._connection() as conn:
            dense = search.vector_search(
                conn, to_pgvector(vector), limit=depth, lang=resolved_lang, law=resolved_law
            )
            by_id = {hit.chunk_id: hit for hit in dense}
            rankings: dict[str, list[int]] = {"dense": [h.chunk_id for h in dense]}

            if self.use_hybrid:
                lexical = search.keyword_search(
                    conn, question, limit=depth, lang=resolved_lang, law=resolved_law
                )
                rankings["lexical"] = [h.chunk_id for h in lexical]
                for hit in lexical:
                    by_id.setdefault(hit.chunk_id, hit)

        fused = reciprocal_rank_fusion(rankings)[:depth]
        candidates: list[Hit] = []
        for chunk_id, score in fused:
            hit = by_id.get(chunk_id)
            if hit is not None:
                hit.score = score
                candidates.append(hit)

        return self.reranker.rerank(question, candidates, top_n)
