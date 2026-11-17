"""RRF and metric tests. Both are pure functions, so these are the cheap safety net."""

from evals.metrics import hit_rate_at_k, markdown_table, mrr, recall_at_k, summarise
from retrieval.fusion import reciprocal_rank_fusion


def test_document_found_by_both_retrievers_wins():
    fused = reciprocal_rank_fusion({"dense": [1, 2, 3], "lexical": [3, 4, 1]})
    assert fused[0][0] in {1, 3}
    assert dict(fused)[1] > dict(fused)[2]


def test_fusion_is_deterministic_and_deduplicated():
    fused = reciprocal_rank_fusion({"a": [7, 7, 8], "b": [8]})
    ids = [chunk_id for chunk_id, _ in fused]
    assert ids.count(7) == 1
    assert set(ids) == {7, 8}
    assert fused == reciprocal_rank_fusion({"a": [7, 7, 8], "b": [8]})


def test_empty_rankings():
    assert reciprocal_rank_fusion({}) == []


def test_recall_at_k_counts_gold_articles_found():
    assert recall_at_k(["a", "b", "c"], ["a", "c"], 2) == 0.5
    assert recall_at_k(["a", "b", "c"], ["a", "c"], 5) == 1.0
    assert recall_at_k(["x"], [], 5) == 0.0


def test_hit_rate_and_mrr():
    assert hit_rate_at_k(["x", "a"], ["a"], 2) == 1.0
    assert hit_rate_at_k(["x", "y"], ["a"], 2) == 0.0
    assert mrr(["x", "y", "a"], ["a"]) == 1 / 3
    assert mrr(["x"], ["a"]) == 0.0


def test_summary_ignores_unanswerable_questions_for_recall():
    rows = [
        {"retrieved": ["ai-act:5"], "relevant": ["ai-act:5"], "type": "factual"},
        {"retrieved": ["gdpr:17"], "relevant": [], "type": "unanswerable"},
    ]
    summary = summarise(rows, ks=(5,))
    assert summary["n_questions"] == 2
    assert summary["n_answerable"] == 1
    assert summary["recall@5"] == 1.0


def test_markdown_table_renders_a_row():
    table = markdown_table({"v0": {"recall@5": 0.42, "recall@10": 0.5, "mrr": 0.31, "n_answerable": 90}})
    assert "| v0 | 0.420 | 0.500 | 0.310 | 90 |" in table
