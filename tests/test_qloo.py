import pytest

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
