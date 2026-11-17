"""API contract tests that need no database."""

from fastapi.testclient import TestClient

from api import db
from api.main import create_app


def test_health_ok_when_db_answers(monkeypatch):
    monkeypatch.setattr(db, "ping", lambda: True)
    with TestClient(create_app()) as client:
        body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"


def test_health_is_degraded_but_still_200_when_db_is_down(monkeypatch):
    monkeypatch.setattr(db, "ping", lambda: False)
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


def test_ask_is_explicitly_not_implemented(monkeypatch):
    monkeypatch.setattr(db, "ping", lambda: True)
    with TestClient(create_app()) as client:
        response = client.post("/api/ask", json={"question": "Which AI practices are prohibited?"})
    assert response.status_code == 501
    assert "not implemented" in response.json()["detail"].lower()


def test_ask_rejects_a_too_short_question():
    with TestClient(create_app()) as client:
        assert client.post("/api/ask", json={"question": "hi"}).status_code == 422


def test_search_reports_retrieval_failure_clearly(monkeypatch):
    class Boom:
        def search(self, *args, **kwargs):
            raise RuntimeError("no chunks indexed")

    monkeypatch.setattr("retrieval.pipeline.Retriever", lambda: Boom())
    with TestClient(create_app()) as client:
        response = client.post("/api/search", json={"question": "Which AI practices are prohibited?"})
    assert response.status_code == 503
    assert "no chunks indexed" in response.json()["detail"]
