"""Request / response models shared by the API and the web client."""

from typing import Literal

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    lang: Literal["en", "fr", "auto"] = "auto"
    session_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class Citation(BaseModel):
    doc: str = Field(description="Human-readable law name, e.g. 'AI Act'")
    article: str = Field(description="Article or Recital identifier, e.g. '5' or 'R12'")
    paragraph: str | None = None
    lang: Literal["en", "fr"]
    chunk_id: int
    url: str | None = None
    snippet: str = ""


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    refused: bool = False
    lang: Literal["en", "fr"]
    latency_ms: int | None = None


class SearchHit(BaseModel):
    chunk_id: int
    doc: str
    article: str | None
    paragraph: str | None
    lang: str
    heading_path: str
    content: str
    score: float
    source_url: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    db: Literal["ok", "unavailable"]
    version: str = "0.1.0"
    week: str = "0-1"
