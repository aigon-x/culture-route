import json
import random

from cultureroute.agent import CultureAgent, MOOD_TAGS
from cultureroute.qloo import QlooClient
from cultureroute.taste import TasteProfile


def _agent(taste=None):
    return CultureAgent(QlooClient(offline=True), taste or TasteProfile())


def test_plan_is_non_empty_and_within_budget():
    route = _agent().plan("Berlin", "curious", 180)
    assert 1 <= len(route.items) <= CultureAgent.MAX_STEPS
    assert sum(i.minutes for i in route.items) <= 180


def test_plan_respects_step_limit():
    route = _agent().plan("Berlin", "reflective", 10_000)
    assert len(route.trace) <= CultureAgent.MAX_STEPS


def test_plan_has_no_duplicates():
    route = _agent().plan("Berlin", "curious", 400)
    names = [i.name for i in route.items]
    assert len(names) == len(set(names))


def test_long_item_is_skipped_not_truncated():
    route = _agent().plan("Berlin", "reflective", 45)
    assert all(i.minutes <= 45 for i in route.items)
    assert all(i.minutes >= 30 for i in route.items)


def test_taste_produces_varied_scores():
    taste = TasteProfile()
    taste.observe(["science"], liked=True)
    taste.observe(["nightlife"], liked=False)
    route = CultureAgent(QlooClient(offline=True), taste).plan("Berlin", "curious", 240)
    scores = {i.score for i in route.items}
    assert len(scores) > 1, "taste should differentiate candidates"


def test_unknown_city_still_terminates():
    route = _agent().plan("Nowhere", "curious", 120)
    assert len(route.trace) <= CultureAgent.MAX_STEPS


def test_no_item_below_zero_score():
    taste = TasteProfile()
    taste.observe(["science"], liked=True)
    route = CultureAgent(QlooClient(offline=True), taste).plan("Berlin", "curious", 240)
    assert all(item.score > 0 for item in route.items)


def _shuffled_agent(seed: int) -> CultureAgent:
    """Same fixtures, different order - what a real API is free to return."""
    from cultureroute.qloo import FIXTURES

    payload = json.loads(open(FIXTURES, encoding="utf-8").read())
    random.Random(seed).shuffle(payload["/v2/insights"]["results"]["entities"])
    client = QlooClient(offline=True)
    client._fixtures = payload
    return CultureAgent(client, TasteProfile())


def test_cold_start_scores_differentiate_by_mood_overlap():
    """An empty profile used to give every mood-matching candidate exactly 0.3."""
    route = CultureAgent(QlooClient(offline=True), TasteProfile()).plan("Berlin", "curious", 240)
    scores = [item.score for item in route.items]
    assert len(set(scores)) > 1, f"cold start is undifferentiated: {scores}"
    top = {t.lower() for t in route.items[0].tags}
    assert len(top & set(MOOD_TAGS["curious"])) >= 2
    assert f"/{len(MOOD_TAGS['curious'])}" in route.items[0].why


def test_plan_does_not_depend_on_entity_order():
    """Ties must be broken by the rules, never by the order the API returned."""
    for mood in ("curious", "reflective"):
        baseline = [(i.kind, i.name, i.score) for i in _shuffled_agent(0).plan("Berlin", mood, 240).items]
        for seed in range(1, 6):
            variant = [(i.kind, i.name, i.score) for i in _shuffled_agent(seed).plan("Berlin", mood, 240).items]
            assert variant == baseline, f"seed {seed} reordered the route for {mood}"
