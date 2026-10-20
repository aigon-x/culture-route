import email.message
import urllib.error

import pytest

import cultureroute.qloo as qloo

from cultureroute.qloo import QlooClient, QlooConfigError


def test_live_mode_without_key_fails_loudly(monkeypatch):
    monkeypatch.delenv("QLOO_API_KEY", raising=False)
    with pytest.raises(QlooConfigError):
        QlooClient(offline=False)


def test_offline_filters_by_entity_type():
    c = QlooClient(offline=True)
    artists = c.get("/v2/insights", **{"filter.type": "urn:entity:artist"})["results"]["entities"]
    places = c.get("/v2/insights", **{"filter.type": "urn:entity:place"})["results"]["entities"]
    assert artists and places
    assert {e["name"] for e in artists}.isdisjoint({e["name"] for e in places})


def test_offline_cache_avoids_second_fetch():
    c = QlooClient(offline=True)
    first = c.get("/v2/insights", **{"filter.type": "urn:entity:book"})
    second = c.get("/v2/insights", **{"filter.type": "urn:entity:book"})
    assert first is second
    assert c.calls == 1


def test_offline_unknown_path_raises():
    with pytest.raises(KeyError):
        QlooClient(offline=True).get("/v2/unknown")


def _error(code: int, retry_after: float | None = None) -> urllib.error.HTTPError:
    headers = email.message.Message()
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return urllib.error.HTTPError("https://hackathon.api.qloo.com/v2/insights", code,
                                  "error", headers, None)


class _Reply:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return b'{"results": {"entities": []}}'


def test_terminal_4xx_is_not_retried(monkeypatch):
    """ARCHITECTURE says 4xx fail immediately; a retried 401 only burns the quota."""
    calls = []

    def boom(request, timeout=0):
        calls.append(request.full_url)
        raise _error(401)

    monkeypatch.setattr(qloo.urllib.request, "urlopen", boom)
    with pytest.raises(RuntimeError) as excinfo:
        QlooClient(api_key="k", retries=2).get("/v2/insights",
                                               **{"filter.type": "urn:entity:place"})
    assert len(calls) == 1
    assert "HTTP 401" in str(excinfo.value)


def test_rate_limit_is_retried_and_retry_after_is_honoured(monkeypatch):
    state = {"calls": 0}

    def flaky(request, timeout=0):
        state["calls"] += 1
        if state["calls"] <= 2:
            raise _error(429, retry_after=0.0)
        return _Reply()

    sleeps = []
    monkeypatch.setattr(qloo.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(qloo.time, "sleep", sleeps.append)
    payload = QlooClient(api_key="k", retries=2).get("/v2/insights")
    assert payload == {"results": {"entities": []}}
    assert state["calls"] == 3
    assert sleeps == [0.0, 0.0]


def test_server_error_is_retried_then_reported(monkeypatch):
    calls = []

    def boom(request, timeout=0):
        calls.append(1)
        raise _error(503)

    monkeypatch.setattr(qloo.urllib.request, "urlopen", boom)
    monkeypatch.setattr(qloo.time, "sleep", lambda seconds: None)
    with pytest.raises(RuntimeError) as excinfo:
        QlooClient(api_key="k", retries=2).get("/v2/insights")
    assert len(calls) == 3
    assert "HTTP 503" in str(excinfo.value)
