# Evaluation method

## Principle

No number lands in the README unless it came from `evals/run.py` on a committed
revision, over the golden set in `evals/golden/questions.jsonl`, with the
configuration named in the result file.

## Layers

| Layer | Metrics | Cost | Runs in CI |
| --- | --- | --- | --- |
| Retrieval | Recall@5, Recall@10, hit rate, MRR | free, deterministic | **yes**, every PR |
| Generation | faithfulness, answer correctness, refusal accuracy | LLM calls | scheduled / manual |
| Judge quality | agreement between the LLM judge and a human spot-check | a few hours of reading | once per judge prompt change |

## Retrieval metrics

- **Recall@k** — of the gold articles for a question, how many appear in the top
  *k* results. Multi-article questions are why this exists alongside hit rate.
- **Hit rate@k** — did *any* gold article appear. Stricter product question,
  easier to move.
- **MRR** — 1 / rank of the first correct article. Punishes "right answer at
  position 30".

Unanswerable questions are excluded from retrieval metrics (there is no gold
article) and used only for refusal accuracy.

## Golden set rules

See `evals/golden/README.md`. The short version:

1. about 40 questions written by hand, the rest generated then **hand-verified**;
2. ~10 % unanswerable;
3. verify against the article text, never from memory;
4. prefer questions a naive retriever fails on.

## Generation metrics

- **Faithfulness** — is every claim in the answer supported by the retrieved
  context? Reported as a rate, with the judge prompt committed.
- **Correctness** — does it agree with the gold answer, including the article
  reference?
- **Refusal accuracy** — on the unanswerable subset, the rate at which the system
  refuses. Reported together with the false-refusal rate on answerable questions,
  because a system that refuses everything scores 100 % on the first metric.
- **Judge agreement** — 20 judge outputs are checked by hand; the agreement rate
  is published next to the judge-derived numbers. Without it, the metric is an
  opinion with a decimal point.

## Ablation

Every change is one row, one commit, and the same golden set:

| Config | Recall@5 | Recall@10 | MRR | Faithfulness | Latency p50 |
| --- | --- | --- | --- | --- | --- |
| v0 vector only | | | | | |
| + hybrid | | | | | |
| + rerank | | | | | |
| + rewrite | | | | | |
| + metadata filters | | | | | |
| + parent-doc expansion | | | | | |

Regressions are reported too. A change that did not help is a finding, not a
failure to hide.

## The CI gate

`evals/results/baseline.json` holds the numbers the gate compares against:

- runs the retrieval eval on a fixed subset (~20 questions);
- fails if `recall@5` or `mrr` drops by more than the tolerance (2 points);
- has no LLM dependency, so it is fast and cannot fail on a 429.

Regenerate the baseline deliberately, in its own commit, with the reason in the
message.
