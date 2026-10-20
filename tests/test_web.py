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
