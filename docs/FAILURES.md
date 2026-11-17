# Failure analysis

Real problems, in the order they were hit, with what they taught. Later entries
come from eval runs; the ones below came from building the ingestion path, which
is where most of them will keep coming from.

---

## 1. The corpus downloaded "successfully" and was empty

**Symptom.** `python -m ingest.cli download` printed six cheerful lines and wrote
six files of 0 bytes. Nothing failed. `sha256=e3b0c44298fc` — the hash of the
empty string — was visible only because the log prints it.

**Cause.** The URL was correct, but the client was not: the EUR-Lex web front end
now answers non-browser requests with HTTP 202 and an AWS WAF JavaScript
challenge. A 202 is a success status, so `raise_for_status()` was happy.

**Fix.** Fetch from the Publications Office Cellar endpoint (`Accept:
application/xhtml+xml`, `Accept-Language: eng|fra`), and validate the payload
before writing it: minimum size, presence of `eli-subdivision`, minimum number of
subdivisions. A cached firewall page is now a hard error.

**Lesson.** "It downloaded" is not evidence. Validate the *content*, not the
status code — especially with a corpus that everything downstream depends on.

---

## 2. French and English produced different retrieval granularity

**Symptom.** For the GDPR, English parsed to 947 units and French to 562, with the
same 99 articles. Lecture of Article 5 showed why: English renders the list items
`(a) … (f)` as separate table cells, French inlines them as
`… doivent être: a) … ; b) … ; c) …` in a single paragraph. The French chunk for
Article 5(1) was 2 106 characters; the English equivalent was eight short units.

**Why it matters.** Recall@5 over the French half of the benchmark would have been
measuring a different chunking strategy than the English half, and a bilingual
comparison would have been meaningless.

**Fix.** Split inline enumerations (`: a) … ; b) …`) into one unit per marker
during parsing, and reattach fragments shorter than 25 characters to the previous
item. After the change: GDPR FR 882 units vs EN 943 — the remaining gap is
translation wording, not structure.

**Lesson.** A "bilingual" corpus is two corpora. Verify that the pipeline produces
comparable structure on both sides before comparing scores, not after.

---

## 3. Every French accent became mojibake in the tests only

**Symptom.** The parser produced correct French from the real documents but the
unit tests failed on `… doivent être:`.

**Cause.** `lxml.html.fromstring()` was handed UTF-8 *bytes* without a document
declaration, and fell back to Latin-1. The real files declare
`encoding="UTF-8"`, so they parsed correctly and hid the bug — the test fixture
did not.

**Fix.** Parse with an explicit `HTMLParser(encoding="utf-8")`.

**Lesson.** The fixture must be parsed the same way as production data, and a
green corpus run does not prove the parser is encoding-safe.

---

## 4. The default database port was already taken

**Symptom.** `docker compose up db` failed with
`ports are not available: … 5433 … permission denied`.

**Cause.** A local PostgreSQL instance (another project) was already listening on
5433; Windows also reserves scattered ranges for Hyper-V, which produces the same
"permission" wording.

**Fix.** The stack defaults to `55432`, which is outside the reserved ranges, and
the port stays configurable through `DB_PORT`.

**Lesson.** Never ship a port default that a developer's laptop may already own;
check `netsh interface ipv4 show excludedportrange` on Windows.

---

## Template for eval-run entries

### N. <one-line symptom, quantified>

**Question that exposed it.** `« … »` (`q042`, type `multi-article`)

**What happened.** Retrieved Articles 6 and 7, not 8; the answer then asserted a
requirement that lives in Article 8.

**Why.** The question used "conformity assessment" while the article says
"assessment of conformity"; the dense leg returned Recital 43, which paraphrases
the same idea more closely.

**Fix.** Parent-document expansion: retrieve at paragraph level, pass the whole
article to the generator. Recall@5 on `multi-article` went 0.61 → 0.78; cost ~340 ms
at p50.

**Lesson.** Check recitals against articles *before* tuning scores: a recital
ranking above its article is a retrieval bug with a legal consequence.
