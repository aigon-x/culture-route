"""Qloo API client with cache and retry, plus an explicit offline fixture mode."""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE = "https://hackathon.api.qloo.com"
FIXTURES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "fixtures", "offline_responses.json")
RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})
MAX_RETRY_AFTER = 5.0


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

    @staticmethod
    def idempotency_key(path: str, params: dict) -> str:
        """Stable key for a read: retries of the same query must hit the cache, not the API."""
        raw = path + "?" + urllib.parse.urlencode(sorted(params.items()))
        return hashlib.sha256(raw.encode()).hexdigest()

    def _key(self, path: str, params: dict) -> str:
        return self.idempotency_key(path, params)

    @staticmethod
    def _filter_offline(payload: dict, params: dict) -> dict:
        """Offline fixtures hold one pool; select the requested entity type.

        Entity ids carry their type (`qloo:artist/...`, `qloo:movie/...`), so the
        offline path mirrors what `filter.type` does on the live API.
        """
        wanted = params.get("filter.type")
        entities = (payload.get("results") or {}).get("entities", [])
        if not wanted or not entities:
            return payload
        prefix = wanted.rsplit(":", 1)[-1]
        picked = [e for e in entities
                  if str(e.get("entity_id", "")).split(":")[-1].split("/")[0] == prefix]
        return {"results": {"entities": picked}}

    def get(self, path: str, **params) -> dict:
        """GET path with cache (120 s); retries only what can succeed on a retry."""
        cache_key = self._key(path, params)
        hit = self._cache.get(cache_key)
        if hit and time.time() - hit[0] < 120:
            return hit[1]
        self.calls += 1
        if self.offline:
            payload = self._fixtures.get(path.split("?")[0])
            if payload is None:
                raise KeyError(f"no offline fixture for {path}")
            payload = self._filter_offline(payload, params)
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
                delay = self._retry_delay(exc, attempt)
                if delay is None or attempt >= self.retries:
                    break
                time.sleep(delay)
        if isinstance(last, urllib.error.HTTPError):
            raise RuntimeError(
                f"Qloo rejected the request: HTTP {last.code} {last.reason} "
                f"(retryable={last.code in RETRYABLE_STATUS})")
        raise RuntimeError(f"Qloo request failed after {self.retries + 1} attempts: {last}")

    @staticmethod
    def _retry_delay(exc: Exception, attempt: int) -> float | None:
        """Seconds to wait before the next attempt; None means this attempt was the last.

        A 401/403/404 will never succeed on a retry, so retrying it only burns the quota
        and delays the error the user needs to read. 429 and 5xx are worth another try,
        and a Retry-After header is an explicit instruction, not a suggestion.
        """
        base = 0.2 * (attempt + 1)
        if not isinstance(exc, urllib.error.HTTPError):
            return base
        if exc.code not in RETRYABLE_STATUS:
            return None
        header = exc.headers.get("Retry-After") if exc.headers else None
        if header:
            try:
                return max(0.0, min(float(header), MAX_RETRY_AFTER))
            except (TypeError, ValueError):
                return base
        return base
