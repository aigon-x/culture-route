from cultureroute.agent import CultureAgent
from cultureroute.qloo import QlooClient
from cultureroute.taste import TasteProfile


def _agent():
    return CultureAgent(QlooClient(offline=True), TasteProfile())


def test_plan_is_non_empty_and_within_budget():
    route = _agent().plan("Berlin", "curious", 180)
    assert 1 <= len(route.items) <= CultureAgent.MAX_STEPS
    assert sum(i.minutes for i in route.items) <= 180


def test_plan_respects_step_limit():
    route = _agent().plan("Berlin", "reflective", 10_000)
    assert len(route.trace) <= CultureAgent.MAX_STEPS


def test_taste_changes_ordering():
    taste = TasteProfile(); taste.observe(["science"], liked=True)
    route = CultureAgent(QlooClient(offline=True), taste).plan("Berlin", "curious", 240)
    names = [i.name for i in route.items]
    assert "Museum für Naturkunde" in names or "The Science of Sound" in names


def test_unknown_city_still_terminates():
    route = _agent().plan("Nowhere", "curious", 120)
    assert len(route.trace) <= CultureAgent.MAX_STEPS


def test_plan_has_no_duplicate_items():
    route = _agent().plan("Berlin", "curious", 400)
    names = [i.name for i in route.items]
    assert len(names) == len(set(names))
