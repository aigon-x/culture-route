import pytest

from cultureroute.qloo import QlooClient, QlooConfigError


def test_live_mode_without_key_fails_loudly(monkeypatch):
    monkeypatch.delenv("QLOO_API_KEY", raising=False)
    with pytest.raises(QlooConfigError):
        QlooClient(offline=False)


def test_offline_returns_fixtures_and_caches(monkeypatch):
    c = QlooClient(offline=True)
    first = c.get("/v2/entities/music", city="Berlin")
    second = c.get("/v2/entities/music", city="Berlin")
    assert first is second  # cache hit, no second fetch
    assert c.calls == 1


def test_offline_unknown_path_raises():
    with pytest.raises(KeyError):
        QlooClient(offline=True).get("/v2/entities/unknown")
