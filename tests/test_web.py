import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web"))
from server import app  # noqa: E402

client = TestClient(app)


def test_index_has_accessible_layout():
    html = client.get("/").text
    assert 'name="viewport"' in html
    assert "prefers-reduced-motion" in html
    assert 'aria-live' in html


def test_plan_endpoint_returns_route(monkeypatch):
    monkeypatch.delenv("QLOO_API_KEY", raising=False)
    payload = client.post("/api/plan", json={"city": "Berlin", "mood": "curious", "minutes": 180}).json()
    assert payload["items"]
    assert payload["mode"].startswith("OFFLINE")


def test_empty_city_is_still_a_200_with_reason(monkeypatch):
    monkeypatch.delenv("QLOO_API_KEY", raising=False)
    response = client.post("/api/plan", json={"city": "Nowhere", "mood": "curious", "minutes": 60})
    assert response.status_code == 200
    assert "trace" in response.json()


def test_oversized_body_is_refused_before_the_agent(monkeypatch):
    """The city is echoed back in the route, so an unbounded body is an echo amplifier."""
    import server as web_server

    def boom(*args, **kwargs):  # pragma: no cover - only on regression
        raise AssertionError("the agent must not see an oversized body")

    monkeypatch.setattr(web_server.CultureAgent, "plan", boom)
    body = '{"city":"' + "x" * (web_server.MAX_REQUEST_BYTES + 10)
    body += '","mood":"curious","minutes":60}'
    response = client.post("/api/plan", content=body, headers={"content-type": "application/json"})
    assert response.status_code == 413


def test_plan_fields_are_bounded():
    assert client.post("/api/plan", json={"city": "x" * 201}).status_code == 422
    assert client.post("/api/plan", json={"minutes": 0}).status_code == 422
    assert client.post("/api/plan", json={"minutes": 5000}).status_code == 422
    assert client.post("/api/plan", json={"mood": "m" * 33}).status_code == 422


def test_content_length_policy():
    import server as web_server

    assert web_server._body_rejection(None).status_code == 411
    assert web_server._body_rejection("not-a-number").status_code == 413
    assert web_server._body_rejection(str(web_server.MAX_REQUEST_BYTES + 1)).status_code == 413
    assert web_server._body_rejection(str(web_server.MAX_REQUEST_BYTES)) is None
