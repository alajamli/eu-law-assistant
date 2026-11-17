"""FastAPI entrypoint.

Week 0 scope: /health and /api/search work; /api/ask is deliberately not wired
until the baseline pipeline exists (Week 1, step 5-6). Returning an explicit 501
is better than a half-working endpoint that would silently poison the evals.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api import db
from api.config import get_settings
from api.schemas import AskRequest, AskResponse, HealthResponse, SearchHit


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    db.close_pool()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="EU-Law Assistant",
        version="0.1.0",
        lifespan=lifespan,
        description=(
            "Bilingual (EN/FR) question answering over the EU AI Act, GDPR and Data Act, "
            "with citations to the exact article and a refusal path when the sources "
            "do not contain the answer."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        db_ok = db.ping()
        return HealthResponse(status="ok" if db_ok else "degraded", db="ok" if db_ok else "unavailable")

    @app.post("/api/search", response_model=list[SearchHit])
    def search(payload: AskRequest) -> list[SearchHit]:
        """Retrieval only. Useful for debugging and for the eval harness."""
        from retrieval.pipeline import Retriever

        try:
            hits = Retriever().search(payload.question, lang=payload.lang, top_n=payload.top_k)
        except Exception as exc:  # noqa: BLE001 - surface a clear message, not a stack trace
            raise HTTPException(status_code=503, detail=f"retrieval unavailable: {exc}") from exc
        return [SearchHit(**hit.as_dict()) for hit in hits]

    @app.post("/api/ask", response_model=AskResponse, status_code=501)
    def ask(_: AskRequest) -> AskResponse:
        raise HTTPException(
            status_code=501,
            detail=(
                "Generation is not implemented yet (Week 1). "
                "POST /api/search already returns retrieved articles."
            ),
        )

    return app


app = create_app()
