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


def _fresh_profile(monkeypatch, tmp_path):
    """Point the web app at an empty profile so a test never mutates state/taste.json."""
    import server as web_server

    path = tmp_path / "taste.json"
    path.write_text('{"weights": {}}', encoding="utf-8")
    monkeypatch.setenv("CULTUREROUTE_TASTE_PATH", str(path))
    monkeypatch.setattr(web_server, "_PROFILE", None)
    monkeypatch.setattr(web_server, "_PROFILE_PATH", None)
    return path


def test_feedback_changes_the_next_route(monkeypatch, tmp_path):
    """The demo used to expose only plan; a rating must move the weights the next plan reads."""
    import json

    path = _fresh_profile(monkeypatch, tmp_path)
    before = client.post("/api/plan", json={"city": "Berlin", "mood": "energetic",
                                           "minutes": 180}).json()
    names_before = [item["name"] for item in before["items"]]

    response = client.post("/api/feedback", json={"tags": ["AMBIENT", " piano ", "slow"],
                                                  "liked": True})
    assert response.status_code == 200
    body = response.json()
    assert body["updated"] == [
        {"tag": "ambient", "before": 0.0, "after": 0.25},
        {"tag": "piano", "before": 0.0, "after": 0.25},
        {"tag": "slow", "before": 0.0, "after": 0.25},
    ]
    assert body["persisted"] is True
    assert json.loads(path.read_text(encoding="utf-8"))["weights"]["ambient"] == 0.25

    after = client.post("/api/plan", json={"city": "Berlin", "mood": "energetic",
                                          "minutes": 180}).json()
    names_after = [item["name"] for item in after["items"]]
    assert names_after != names_before
    assert any(item["why"].startswith("affinity 0.25") for item in after["items"])
    assert after["taste"][0] == {"tag": "ambient", "weight": 0.25}


def test_feedback_needs_a_real_tag(monkeypatch, tmp_path):
    _fresh_profile(monkeypatch, tmp_path)
    assert client.post("/api/feedback", json={"tags": ["   "], "liked": True}).status_code == 422
    assert client.post("/api/feedback", json={"tags": [], "liked": True}).status_code == 422


def test_taste_endpoint_reports_the_same_profile_the_plan_uses(monkeypatch, tmp_path):
    _fresh_profile(monkeypatch, tmp_path)
    assert client.get("/api/taste").json()["top"] == []
    client.post("/api/feedback", json={"tags": ["science"], "liked": True})
    assert client.get("/api/taste").json()["top"] == [{"tag": "science", "weight": 0.25}]
    plan = client.post("/api/plan", json={"city": "Berlin", "mood": "curious",
                                         "minutes": 120}).json()
    assert {"tag": "science", "weight": 0.25} in plan["taste"]


def test_index_lets_a_visitor_rate_a_stop():
    html = client.get("/").text
    assert "/api/feedback" in html
    assert "More like this" in html and "Not for me" in html
    assert 'id="taste"' in html
