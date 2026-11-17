"""Run the retrieval evaluation over the golden set.

    python -m evals.run --config v0 --no-hybrid --no-rerank
    python -m evals.run --config hybrid+rerank

Writes evals/results/<config>.json plus a markdown table, keyed by config name.
The git commit is recorded so a result can always be traced back to code.

Generation metrics (faithfulness, correctness, judge agreement) need an LLM and
are added in Week 2 step 3; this module only scores retrieval, which is the part
that can run for free on every PR.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from evals.golden import GOLDEN_PATH, GoldenQuestion, load_golden
from evals.metrics import markdown_table, summarise
from ingest.embed import get_embedder

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
        ).stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def _key(hit) -> str:
    return f"{hit.doc_slug}:{hit.article}"


def evaluate(
    questions: list[GoldenQuestion],
    retriever,
    max_k: int = 10,
) -> dict:
    rows = []
    for item in questions:
        hits = retriever.search(item.question, lang=item.lang, top_n=max_k)
        rows.append(
            {
                "id": item.id,
                "question": item.question,
                "lang": item.lang,
                "type": item.type,
                "relevant": item.gold_articles,
                "retrieved": [_key(h) for h in hits],
                "retrieved_chunk_ids": [h.chunk_id for h in hits],
            }
        )
    return {"summary": summarise(rows), "rows": rows}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="evals", description=__doc__)
    ap.add_argument("--config", default="v0", help="name of this configuration (result file name)")
    ap.add_argument("--golden", type=Path, default=GOLDEN_PATH)
    ap.add_argument("--include-draft", action="store_true", help="score unverified questions too")
    ap.add_argument("--no-hybrid", action="store_true")
    ap.add_argument("--no-rerank", action="store_true")
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--embedding-backend", default="local", choices=["local", "hashing"])
    ap.add_argument("--out-dir", type=Path, default=RESULTS_DIR)
    args = ap.parse_args(argv)

    questions = load_golden(args.golden, include_draft=args.include_draft)
    if not questions:
        print("No verified questions yet. Add rows to evals/golden/questions.jsonl and set status=verified.")
        return 2

    embedder = get_embedder(args.embedding_backend)
    if not getattr(embedder, "is_real", False):
        print(
            "Refusing to record numbers with the dev hashing embedder: they would be meaningless.\n"
            "Use --embedding-backend local (downside: downloads bge-m3).",
        )
        return 2

    from retrieval.pipeline import Retriever

    retriever = Retriever(embedder=embedder, use_hybrid=not args.no_hybrid, use_rerank=not args.no_rerank)
    result = evaluate(questions, retriever, max_k=args.top_k)

    payload = {
        "config": args.config,
        "commit": _git_commit(),
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "hybrid": not args.no_hybrid,
        "rerank": not args.no_rerank,
        **result["summary"],
        "rows": result["rows"],
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_json = args.out_dir / f"{args.config}.json"
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    table = markdown_table({args.config: result["summary"]})
    (args.out_dir / f"{args.config}.md").write_text(table + "\n", encoding="utf-8")
    print(table)
    print(f"\nwrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
