"""Taste profile: a sparse tag -> weight vector updated from explicit feedback."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class TasteProfile:
    weights: dict[str, float] = field(default_factory=dict)

    def observe(self, tags: Iterable[str], liked: bool) -> None:
        """Update weights. Likes add, dislikes subtract; values stay in [-1, 1]."""
        delta = 0.25 if liked else -0.35
        for tag in tags:
            value = self.weights.get(tag.lower(), 0.0) + delta
            self.weights[tag.lower()] = max(-1.0, min(1.0, value))

    def affinity(self, tags: Iterable[str]) -> float:
        """Cosine-free affinity in [-1, 1]: mean weight of the item's tags."""
        values = [self.weights.get(t.lower(), 0.0) for t in tags]
        if not values:
            return 0.0
        return sum(values) / len(values)

    def top(self, n: int = 5) -> list[tuple[str, float]]:
        return sorted(self.weights.items(), key=lambda kv: kv[1], reverse=True)[:n]

    def to_json(self) -> str:
        return json.dumps({'weights': self.weights}, ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_json(cls, raw: str) -> 'TasteProfile':
        return cls(weights={k: float(v) for k, v in json.loads(raw).get('weights', {}).items()})
