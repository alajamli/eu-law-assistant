# Measured runs

One JSON + one Markdown file per configuration. `evals/run.py` writes both and
records the git commit, so a number can always be traced back to code.

Naming: `v0`, `hybrid`, `hybrid-rerank`, `hybrid-rerank-rewrite`, …

`baseline.json` is the file the CI eval gate compares against. Regenerate it
deliberately, in its own commit, with the reason in the commit message.
