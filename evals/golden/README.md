# Golden set

One JSON object per line in `questions.jsonl`. This file is the benchmark: every
number in the README comes from it, so it is versioned like code.

## Row schema

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | stable, never reused |
| `question` | string | exactly how a user would type it |
| `lang` | `en` \| `fr` | language of the question |
| `type` | `factual` \| `multi-article` \| `cross-lingual` \| `unanswerable` | drives the per-type breakdown |
| `gold_articles` | list | `"<slug>:<article>"`, e.g. `"gdpr:17"`. Empty for `unanswerable`. |
| `gold_answer` | string \| null | short reference answer, used by the LLM judge |
| `status` | `draft` \| `verified` | only `verified` rows are scored |
| `notes` | string \| null | why the question is interesting |

Slugs: `ai-act`, `gdpr`, `data-act`. Recitals are written `R12`.

## Rules

1. **Write about 40 yourself, generate the rest, then hand-verify every one.**
   A generated set that was never checked produces numbers you cannot defend —
   the first thing a reviewer will ask is "who checked these?".
2. **~10 % unanswerable.** Without them, refusal accuracy is unmeasurable and the
   system learns to always answer.
3. **Verify against the article text, not against memory.** Open the EUR-Lex page
   and confirm the article actually answers the question.
4. **Keep it bilingual and roughly balanced** (≈50 EN / ≈50 FR), with at least
   10 `cross-lingual` rows (question in one language, gold article checked in
   both).
5. **Prefer questions where a naive retriever fails** — "the exception to the
   prohibition", "which article applies to X". Easy questions inflate Recall@5.

## Adding rows

Append to `questions.jsonl` with `"status": "draft"`, run
`python -m evals.run --include-draft` to see what retrieval does, then flip to
`"verified"` once you have read the source paragraph.
