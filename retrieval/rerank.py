"""Reranking with bge-reranker-v2-m3, behind a swappable interface.

Importing torch takes seconds and ~2 GB, so the real reranker is lazy and the
default in tests/dev is a no-op that preserves the fused order.
"""

from __future__ import annotations

from typing import Protocol

from ingest.models import Hit


class Reranker(Protocol):
    name: str

    def rerank(self, query: str, hits: list[Hit], top_n: int) -> list[Hit]: ...


class NoopReranker:
    """Keeps the fusion order. Used when RERANK_ENABLED=false and in tests."""

    name = "none"

    def rerank(self, query: str, hits: list[Hit], top_n: int) -> list[Hit]:
        return hits[:top_n]


class CrossEncoderReranker:
    name = "cross-encoder"

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3") -> None:
        from sentence_transformers import CrossEncoder  # lazy

        self.name = model_name
        self._model = CrossEncoder(model_name)

    def rerank(self, query: str, hits: list[Hit], top_n: int) -> list[Hit]:
        if not hits:
            return []
        scores = self._model.predict([(query, hit.content) for hit in hits])
        for hit, score in zip(hits, scores, strict=True):
            hit.score = float(score)
        return sorted(hits, key=lambda h: h.score, reverse=True)[:top_n]


def get_reranker(enabled: bool, model_name: str = "BAAI/bge-reranker-v2-m3") -> Reranker:
    return CrossEncoderReranker(model_name) if enabled else NoopReranker()
