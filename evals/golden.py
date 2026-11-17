"""Golden set schema and loader.

Rule from the roadmap, enforced by `status`: a question only counts in the scores
once a human has verified its gold articles. Draft rows are visible in the file
but excluded from runs unless `--include-draft` is passed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "questions.jsonl"

QuestionType = Literal["factual", "multi-article", "cross-lingual", "unanswerable"]


class GoldenQuestion(BaseModel):
    id: str
    question: str = Field(min_length=5)
    lang: Literal["en", "fr"]
    type: QuestionType
    # "ai-act:5" — slug and article identifier, matching Hit.doc_slug / Hit.article
    gold_articles: list[str] = Field(default_factory=list)
    gold_answer: str | None = None
    status: Literal["draft", "verified"] = "draft"
    notes: str | None = None

    @model_validator(mode="after")
    def _check(self) -> GoldenQuestion:
        if self.type != "unanswerable" and not self.gold_articles:
            raise ValueError(f"{self.id}: an answerable question needs gold_articles")
        if self.type == "unanswerable" and self.gold_articles:
            raise ValueError(f"{self.id}: unanswerable questions must not list gold_articles")
        for ref in self.gold_articles:
            if ":" not in ref:
                raise ValueError(f"{self.id}: gold article '{ref}' must look like 'ai-act:5'")
        return self


def load_golden(path: Path = GOLDEN_PATH, include_draft: bool = False) -> list[GoldenQuestion]:
    questions: list[GoldenQuestion] = []
    with path.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                questions.append(GoldenQuestion(**json.loads(line)))
            except Exception as exc:  # noqa: BLE001 - report the offending line
                raise ValueError(f"{path.name}:{line_no}: {exc}") from exc
    if include_draft:
        return questions
    return [q for q in questions if q.status == "verified"]
