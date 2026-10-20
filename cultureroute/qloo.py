"""Qloo API client with cache and retry, plus an explicit offline fixture mode."""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE = "https://api.qloo.com"
FIXTURES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "fixtures", "offline_responses.json")


class QlooConfigError(RuntimeError):
    """Raised when live mode is requested without QLOO_API_KEY."""


class QlooClient:
    def __init__(self, api_key: str | None = None, base_url: str = DEFAULT_BASE,
                 offline: bool = False, timeout: float = 10.0, retries: int = 2):
        self.api_key = api_key if api_key is not None else os.getenv("QLOO_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.offline = offline
        self.timeout = timeout
        self.retries = retries
        self._cache: dict[str, tuple[float, dict]] = {}
        self.calls = 0
        self._fixtures = self._load_fixtures() if offline else {}
        if not self.offline and not self.api_key:
            raise QlooConfigError(
                "QLOO_API_KEY is not set. Run with --offline for the deterministic fixture mode, "
                "or export the key from https://docs.qloo.com before using --live."
            )

    @staticmethod
    def _load_fixtures() -> dict:
        with open(FIXTURES, encoding="utf-8") as fh:
            return json.load(fh)

    def _key(self, path: str, params: dict) -> str:
        raw = path + "?" + urllib.parse.urlencode(sorted(params.items()))
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, path: str, **params) -> dict:
        """GET path with cache (120 s) and retry on 5xx/timeout."""
        cache_key = self._key(path, params)
        hit = self._cache.get(cache_key)
        if hit and time.time() - hit[0] < 120:
            return hit[1]
        self.calls += 1
        if self.offline:
            payload = self._fixtures.get(path.split("?")[0])
            if payload is None:
                raise KeyError(f"no offline fixture for {path}")
            self._cache[cache_key] = (time.time(), payload)
            return payload
        url = f"{self.base_url}{path}?{urllib.parse.urlencode(params)}"
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                req = urllib.request.Request(url, headers={"x-api-key": self.api_key,
                                                           "accept": "application/json"})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                self._cache[cache_key] = (time.time(), payload)
                return payload
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
                last = exc
                if attempt < self.retries:
                    time.sleep(0.2 * (attempt + 1))
        raise RuntimeError(f"Qloo request failed after {self.retries + 1} attempts: {last}")
