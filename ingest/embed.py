"""Embedding backends.

`BGEM3Embedder` is the real one (multilingual, 1024 dims). It is imported lazily
because sentence-transformers + torch are ~2 GB of dependencies that unit tests
and CI must not pay for.

`HashingEmbedder` is a deterministic stand-in (no model download, no GPU). It
produces *semantically meaningless but repeatable* vectors, which is exactly what
you want to test that schema, SQL and the ingestion path work end to end. It is
never used for evaluation numbers — `evals/run.py` refuses to score with it.
"""

from __future__ import annotations

import hashlib
from typing import Protocol

import numpy as np


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashingEmbedder:
    """Deterministic bag-of-tokens projection. DEV / TEST ONLY."""

    is_real = False

    def __init__(self, dim: int = 1024) -> None:
        self.dim = dim
        self.name = f"hashing-{dim} (dev only)"

    def _vector(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        for token in text.lower().split():
            seed = int.from_bytes(hashlib.blake2b(token.encode(), digest_size=8).digest(), "little")
            rng = np.random.default_rng(seed)
            vec += rng.standard_normal(self.dim, dtype=np.float32)
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t).tolist() for t in texts]


class BGEM3Embedder:
    """BAAI/bge-m3 via sentence-transformers."""

    is_real = True

    def __init__(self, model_name: str = "BAAI/bge-m3", batch_size: int = 16) -> None:
        from sentence_transformers import SentenceTransformer  # lazy

        self.name = model_name
        self.batch_size = batch_size
        self._model = SentenceTransformer(model_name)
        self.dim = int(self._model.get_sentence_embedding_dimension())

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 32,
        )
        return [v.tolist() for v in vectors]


def get_embedder(backend: str = "local", model_name: str = "BAAI/bge-m3", dim: int = 1024) -> Embedder:
    if backend in {"local", "bge-m3", "sentence-transformers"}:
        try:
            return BGEM3Embedder(model_name)
        except ImportError as exc:
            raise RuntimeError(
                "EMBEDDING_BACKEND=local needs the ML extra: pip install -e '.[ml]'. "
                "For a torch-free demo, set EMBEDDING_BACKEND=hashing and re-index — but the "
                "query and the index must use the same backend, so never mix them."
            ) from exc
    if backend in {"hashing", "dev", "test"}:
        return HashingEmbedder(dim)
    raise ValueError(f"unknown EMBEDDING_BACKEND '{backend}' (use 'local' or 'hashing')")


def to_pgvector(vector: list[float]) -> str:
    """pgvector's text representation, cast with ::vector in SQL."""
    return "[" + ",".join(f"{x:.7f}" for x in vector) + "]"
