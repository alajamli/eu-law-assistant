"""Reciprocal Rank Fusion.

RRF combines rankings without needing comparable scores across retrievers:

    score(d) = sum over lists of 1 / (k + rank(d))

k=60 is the value from the original Cormack et al. paper and is fine here; keep
it fixed so week-over-week ablations measure retrieval, not tuning noise.
"""

from __future__ import annotations

from collections import defaultdict


def reciprocal_rank_fusion(rankings: dict[str, list[int]], k: int = 60) -> list[tuple[int, float]]:
    """Fuse {retriever_name: [chunk_id, ...]} into [(chunk_id, score), ...] best first."""
    scores: dict[int, float] = defaultdict(float)
    for ids in rankings.values():
        for rank, chunk_id in enumerate(ids, start=1):
            scores[chunk_id] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
