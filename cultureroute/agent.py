"""Plan-act-observe loop: propose categories, query Qloo, score, refine, emit a route."""
from __future__ import annotations

from dataclasses import dataclass, field

from .qloo import QlooClient
from .taste import TasteProfile

CATEGORY_PATHS = {
    "music": "/v2/entities/music",
    "film": "/v2/entities/movie",
    "book": "/v2/entities/book",
    "place": "/v2/entities/place",
}
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
        path = CATEGORY_PATHS[kind]
        payload = self.client.get(path, city=city, limit=12)
        return payload.get("results", payload.get("entities", []))

    def plan(self, city: str, mood: str, minutes: int) -> Route:
        route = Route(city=city, mood=mood)
        mood_tags = MOOD_TAGS.get(mood, [])
        budget = minutes
        used: set[str] = set()
        for step in range(self.MAX_STEPS):
            if budget <= 0:
                break
            kind = ["music", "place", "film", "book", "place", "music"][step % 6]
            try:
                candidates = self._query(kind, city)
            except (KeyError, RuntimeError) as exc:
                route.trace.append({"step": step, "kind": kind, "error": str(exc)[:120]})
                continue
            scored = []
            for entity in candidates:
                name = entity.get("name", "unknown")
                if name in used:
                    continue
                tags = [str(t).lower() for t in entity.get("tags", [])]
                affinity = self.taste.affinity(tags)
                mood_bonus = 0.3 if set(tags) & set(mood_tags) else 0.0
                scored.append((affinity + mood_bonus, entity, tags))
            scored.sort(key=lambda row: row[0], reverse=True)
            best = scored[0] if scored else None
            if not best or best[0] <= 0:
                route.trace.append({"step": step, "kind": kind, "decision": "skip",
                                    "reason": "no candidate above zero affinity"})
                continue
            score, entity, tags = best
            duration = min(int(entity.get("typical_minutes", 45)), budget)
            used.add(entity.get("name", "unknown"))
            route.items.append(RouteItem(
                kind=kind, name=entity.get("name", "unknown"), tags=tags,
                score=round(float(score), 3), minutes=duration,
                why=f"affinity {self.taste.affinity(tags):.2f}, mood match "
                    f"{'yes' if set(tags) & set(mood_tags) else 'no'}"))
            route.trace.append({"step": step, "kind": kind, "decision": "accept",
                                "name": entity.get("name"), "score": round(float(score), 3)})
            budget -= duration
        return route
