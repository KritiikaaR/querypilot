import pytest
from fastapi.testclient import TestClient

from app.agent import TextToSQLAgent
from app.main import app, get_agent, get_db


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def use_llm(db, llm):
    app.dependency_overrides[get_agent] = lambda: TextToSQLAgent(db, llm, max_rows=50, timeout_ms=1000)


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_schema_endpoint(client):
    names = {t["name"] for t in client.get("/api/schema").json()["tables"]}
    assert names == {"pizza_types", "pizzas", "orders", "order_details"}


def test_examples_endpoint(client):
    assert len(client.get("/api/examples").json()["examples"]) >= 3


def test_query_endpoint(client, db, fake_llm):
    use_llm(db, fake_llm([{"sql": "SELECT COUNT(*) AS n FROM pizzas", "explanation": "Counts menu items."}]))
    body = client.post("/api/query", json={"question": "How many menu items?"}).json()
    assert body["status"] == "ok" and body["rows"] == [[96]] and body["sql"].startswith("SELECT")


def test_query_endpoint_works_without_glossary(client, db, fake_llm, tmp_path):
    llm = fake_llm([{"sql": "SELECT COUNT(*) AS n FROM pizzas", "explanation": "Counts menu items."}])
    app.dependency_overrides[get_agent] = lambda: TextToSQLAgent(db, llm, glossary_path=tmp_path / "missing.md")
    body = client.post("/api/query", json={"question": "How many menu items?"}).json()
    assert body["status"] == "ok" and body["rows"] == [[96]]


def test_query_validates_input(client, db, fake_llm):
    use_llm(db, fake_llm([]))
    assert client.post("/api/query", json={"question": ""}).status_code == 422
    assert client.post("/api/query", json={"question": "x" * 501}).status_code == 422


def test_missing_api_key_returns_503(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r = client.post("/api/query", json={"question": "How many menu items?"})
    assert r.status_code == 503 and "OPENAI_API_KEY" in r.json()["detail"]


def test_upstream_model_failure_returns_502(client, db):
    class Boom:
        def complete(self, messages):
            raise TimeoutError("model timed out")

    use_llm(db, Boom())
    r = client.post("/api/query", json={"question": "How many menu items?"})
    assert r.status_code == 502 and "TimeoutError" in r.json()["detail"]
