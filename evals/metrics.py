"""Retrieval metrics.

These are deterministic, free and fast, which is why they — not LLM-judge
metrics — are what the pull-request eval gate runs.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence


def recall_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    relevant_set = set(relevant)
    if not relevant_set:
        return 0.0
    found = relevant_set & set(retrieved[:k])
    return len(found) / len(relevant_set)


def hit_rate_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    return 1.0 if set(retrieved[:k]) & set(relevant) else 0.0


def mrr(retrieved: Sequence[str], relevant: Iterable[str]) -> float:
    relevant_set = set(relevant)
    for rank, key in enumerate(retrieved, start=1):
        if key in relevant_set:
            return 1.0 / rank
    return 0.0


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def summarise(rows: list[dict], ks: Sequence[int] = (5, 10)) -> dict:
    """rows: [{"retrieved": [...], "relevant": [...], "type": ..., "lang": ...}]"""
    answerable = [r for r in rows if r["relevant"]]
    summary: dict = {"n_questions": len(rows), "n_answerable": len(answerable)}
    for k in ks:
        summary[f"recall@{k}"] = round(
            mean(recall_at_k(r["retrieved"], r["relevant"], k) for r in answerable), 4
        )
        summary[f"hit_rate@{k}"] = round(
            mean(hit_rate_at_k(r["retrieved"], r["relevant"], k) for r in answerable), 4
        )
    summary["mrr"] = round(mean(mrr(r["retrieved"], r["relevant"]) for r in answerable), 4)

    by_type: dict[str, list[dict]] = {}
    for row in rows:
        by_type.setdefault(row.get("type") or "unknown", []).append(row)
    summary["by_type"] = {
        key: {
            "n": len(group),
            "recall@5": round(mean(recall_at_k(r["retrieved"], r["relevant"], 5) for r in group), 4),
            "mrr": round(mean(mrr(r["retrieved"], r["relevant"]) for r in group), 4),
        }
        for key, group in sorted(by_type.items())
    }
    return summary


def markdown_table(results: dict[str, dict]) -> str:
    """results: {config_name: summary}. Fill this in week over week."""
    header = "| Config | Recall@5 | Recall@10 | MRR | n |\n| --- | --- | --- | --- | --- |"
    lines = [header]
    for config, summary in results.items():
        lines.append(
            f"| {config} | {summary.get('recall@5', 0):.3f} | {summary.get('recall@10', 0):.3f} "
            f"| {summary.get('mrr', 0):.3f} | {summary.get('n_answerable', 0)} |"
        )
    return "\n".join(lines)
