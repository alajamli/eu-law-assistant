"""Embedding helpers: the dev embedder must be deterministic, and pgvector
literals must parse."""

import math

from ingest.embed import HashingEmbedder, to_pgvector


def test_hashing_embedder_is_deterministic_and_normalised():
    embedder = HashingEmbedder(dim=64)
    first = embedder.embed(["Article 5 prohibits social scoring."])[0]
    second = embedder.embed(["Article 5 prohibits social scoring."])[0]
    assert first == second
    assert math.isclose(sum(v * v for v in first), 1.0, rel_tol=1e-5)


def test_different_texts_get_different_vectors():
    embedder = HashingEmbedder(dim=64)
    a, b = embedder.embed(["prohibited practices", "maximum fine"])
    assert a != b


def test_pgvector_literal_format():
    literal = to_pgvector([0.5, -0.25])
    assert literal == "[0.5000000,-0.2500000]"
    assert literal.startswith("[") and literal.endswith("]")
