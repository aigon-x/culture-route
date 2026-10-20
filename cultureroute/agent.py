"""Plan-act-observe loop over Qloo /v2/insights.

Each step asks Qloo for one entity type in the city, scores what comes back against the
taste profile and the mood, and skips a candidate that does not fit the remaining time
instead of truncating it (a 60-minute film is not a 20-minute stop).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .qloo import QlooClient
from .taste import TasteProfile

FILTER_TYPES = {
    "music": "urn:entity:artist",
    "film": "urn:entity:movie",
    "book": "urn:entity:book",
    "place": "urn:entity:place",
}
DEFAULT_MINUTES = {"music": 35, "film": 60, "book": 30, "place": 40}
MOOD_TAGS = {
    "reflective": ["ambient", "documentary", "essay", "museum", "slow"],
    "energetic": ["electronic", "action", "thriller", "live-music", "nightlife"],
    "curious": ["science", "history", "biography", "gallery", "workshop"],
}


@dataclass
class RouteItem:
    kind: str
    name: str
    tags: list[str]
    score: float
    minutes: int
    why: str


@dataclass
class Route:
    city: str
    mood: str
    items: list[RouteItem] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"city": self.city, "mood": self.mood,
                "items": [i.__dict__ for i in self.items], "trace": self.trace}


class CultureAgent:
    MAX_STEPS = 6

    def __init__(self, client: QlooClient, taste: TasteProfile):
        self.client = client
        self.taste = taste

    def _query(self, kind: str, city: str) -> list[dict]:
        interests = [t for t, w in self.taste.top(5) if w > 0]
        params = {
            "filter.type": FILTER_TYPES[kind],
            "filter.location.query": city,
            "feature.explainability": "true",
        }
        if interests:
            params["signal.interests"] = ",".join(interests)
        payload = self.client.get("/v2/insights", **params)
        results = payload.get("results", {})
        return results.get("entities", []) if isinstance(results, dict) else results

    def _score(self, entity: dict, mood_tags: list[str]) -> tuple[float, list[str]]:
        tags = [str(t).lower() for t in entity.get("tags", [])]
        affinity = self.taste.affinity(tags)
        mood_bonus = 0.3 if set(tags) & set(mood_tags) else 0.0
        return affinity + mood_bonus, tags

    def plan(self, city: str, mood: str, minutes: int) -> Route:
        route = Route(city=city, mood=mood)
        mood_tags = MOOD_TAGS.get(mood, [])
        budget = minutes
        used: set[str] = set()
        exhausted: set[str] = set()
        order = ["place", "music", "film", "book", "place", "music"]
        for step in range(self.MAX_STEPS):
            if budget <= 0:
                break
            kind = next((k for k in order[step:] + order[:step] if k not in exhausted), None)
            if kind is None:
                route.trace.append({"step": step, "decision": "stop",
                                    "reason": "all entity types exhausted"})
                break
            try:
                candidates = self._query(kind, city)
            except (KeyError, RuntimeError) as exc:
                exhausted.add(kind)
                route.trace.append({"step": step, "kind": kind, "error": str(exc)[:120]})
                continue
            if not candidates:
                exhausted.add(kind)
                route.trace.append({"step": step, "kind": kind, "decision": "skip",
                                    "reason": "no entities returned"})
                continue
            best = None
            for entity in candidates:
                key = entity.get("entity_id") or entity.get("name", "")
                if key in used:
                    continue
                score, tags = self._score(entity, mood_tags)
                duration = int((entity.get("properties") or {}).get(
                    "typical_minutes", DEFAULT_MINUTES[kind]))
                if duration > budget:
                    continue
                if best is None or score > best[0]:
                    best = (score, entity, tags, duration)
            if best is None or best[0] <= 0:
                route.trace.append({"step": step, "kind": kind, "decision": "skip",
                                    "reason": "no candidate fits the time budget with positive affinity"})
                continue
            score, entity, tags, duration = best
            used.add(entity.get("entity_id") or entity.get("name", ""))
            route.items.append(RouteItem(
                kind=kind, name=entity.get("name", "unknown"), tags=tags,
                score=round(float(score), 3), minutes=duration,
                why=f"affinity {self.taste.affinity(tags):.2f}, mood match "
                    f"{'yes' if set(tags) & set(mood_tags) else 'no'}"))
            route.trace.append({"step": step, "kind": kind, "decision": "accept",
                                "name": entity.get("name"), "score": round(float(score), 3)})
            budget -= duration
        return route
