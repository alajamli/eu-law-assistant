# Decisions

Short ADRs. One entry per decision that would be expensive to reverse, with the
reason and what would make us revisit it.

---

## ADR-001 — Postgres + pgvector for all three stores

**Decision.** One Postgres holds vectors, lexical index, chat history and caches.

**Why.** A second service (Qdrant, Weaviate) would be another thing to deploy,
secure and explain. Postgres is also the stack recruiters recognise, and it lets
hybrid search be a single SQL query family instead of two systems glued together
in Python.

**Revisit if.** Recall plateaus and the HNSW index becomes the measured
bottleneck at the target corpus size.

---

## ADR-002 — Chunk on legal structure, not on a token count

**Decision.** One chunk per article paragraph (grouped while they fit in
~1400 characters), each prefixed with its heading breadcrumb. Recitals are chunked
too but flagged `is_recital`.

**Why.** Fixed 500-token windows cut mid-sentence across article boundaries, and
a citation then points at a fragment. Legal text already has a natural unit. The
breadcrumb is what lets a chunk be read in isolation — and it is a cheap fix for
the "context stripped away" failure the roadmap warns about.

**Revisit if.** The Week 3 ablation shows fixed-size chunks scoring better. That
would be worth reporting, not hiding.

---

## ADR-003 — Retrieval and generation metrics are gated differently

**Decision.** The pull-request gate runs retrieval metrics only (Recall@k, MRR,
hit rate). Faithfulness, correctness and judge agreement run on a schedule or on
demand.

**Why.** An LLM-judge gate makes CI slow, flaky and expensive, and blocks merges
when the provider has an outage — which teaches you to ignore the gate. Retrieval
metrics are deterministic, free and enough to catch "this PR made search worse".

**Revisit if.** A local judge model becomes cheap enough to run in CI reliably.

---

## ADR-004 — Embeddings and reranking are not served from the API container

**Decision.** The API image installs core dependencies only. The ML extras live
behind the `ml` extra and are used offline (ingestion, eval runs). For a deployed
demo, embeddings for the fixed corpus are **precomputed at build/ingest time**, and
reranking either runs on a larger instance or is disabled with a documented
trade-off.

**Why.** `bge-m3` (~2.2 GB) plus `bge-reranker-v2-m3` (~2.3 GB) do not fit in a
256–512 MB free-tier container. Pretending otherwise produces a deploy that dies
in Week 5. This is a real constraint the roadmap does not mention.

**Revisit if.** We move to a paid instance with ≥4 GB, or to a hosted
embedding/rerank API — then measure the latency/cost delta.

---

## ADR-005 — Langfuse Cloud, not self-hosted, for the demo

**Decision.** Tracing goes through an interface; local development points at
Langfuse Cloud's free tier, and tracing can be disabled with env vars.

**Why.** Self-hosted Langfuse now needs Postgres + ClickHouse + Redis + object
storage. That is a second product to operate, and it would not fit beside the API
on a free tier.

**Revisit if.** Tracing data must stay in-house for a client.

---

## ADR-006 — Cache LLM and embedding calls in Postgres

**Decision.** `llm_cache` and `embedding_cache` are keyed by content hash and
shared by the API and the eval harness.

**Why.** The Groq free tier is the binding constraint: a full eval run is
thousands of calls, and re-scoring an unchanged configuration must cost nothing.
Caching also makes eval runs reproducible when the provider's model updates.

**Revisit if.** We pay for a provider with no meaningful rate limit and want
fresh samples per run — then the cache becomes opt-in for generation only.

---

## ADR-007 — Language and law detection are rule-based

**Decision.** Stop-word scoring for language, regex for the target law. No LLM
call on the hot path.

**Why.** It is free, fast and deterministic, and its failures are visible in
tests. The LLM rewrite that *is* worth having (standalone query for multi-turn)
is a separate, measured step in Week 3.

---

## ADR-008 — Recitals are retrievable but never presented as binding law

**Decision.** Recitals are ingested with `is_recital = true`, citeable as
"Recital 12", and excluded from the answer's legal claims where an article covers
the same point.

**Why.** "The AI Act says in Recital 12…" is not a legal obligation. Mixing the
two is the most likely way this project would look naive to a lawyer or a
reviewer — and it is a good, honest failure-analysis story for the README.

---

## ADR-009 — Fetch from the Publications Office Cellar, not the EUR-Lex front end

**Decision.** Download from `publications.europa.eu/resource/celex/{CELEX}` with
`Accept: application/xhtml+xml` and `Accept-Language: eng|fra`. Links shown to
users still point at the human EUR-Lex page.

**Why.** The EUR-Lex web front end sits behind an AWS WAF: a scripted request gets
HTTP 202 and a JavaScript challenge, not the document. The Cellar endpoint serves
the same text with the same ELI markup, without a browser, and is the route the
Publications Office intends machines to use. This was found by testing, when the
first download produced six 0-byte files with a "successful" run.

**Consequence.** `ingest/fetch.py` now validates every payload (size, ELI markup,
minimum subdivision count) and refuses to cache a challenge page. Fetching
`text/html` from Cellar returns 404, so the `Accept` header is load-bearing.

**Revisit if.** EUR-Lex publishes a stable official API with structure-preserving
output; the parser is isolated enough to swap the source in one module.

