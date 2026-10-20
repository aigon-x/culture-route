"""Small web surface for CultureRoute: one page, one JSON endpoint, no build step."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from cultureroute.agent import CultureAgent
from cultureroute.qloo import QlooClient
from cultureroute.taste import TasteProfile

HERE = Path(__file__).resolve().parent
app = FastAPI(title="CultureRoute", version="0.2.0")


MAX_REQUEST_BYTES = 16 * 1024
MAX_DRAIN_BYTES = 256 * 1024
MAX_CITY_CHARS = 200


class PlanRequest(BaseModel):
    city: str = Field(default="Berlin", max_length=MAX_CITY_CHARS)
    mood: str = Field(default="curious", max_length=32)
    minutes: int = Field(default=180, ge=5, le=1440)


def _body_rejection(content_length: str | None) -> JSONResponse | None:
    """Decide on the header alone: the body is echoed back in the route, so it is capped."""
    if content_length is None:
        return JSONResponse(status_code=411,
                            content={"detail": "Content-Length is required for /api/plan."})
    if not content_length.isdigit() or int(content_length) > MAX_REQUEST_BYTES:
        return JSONResponse(status_code=413,
                            content={"detail": "Plan body is larger than 16 KB."})
    return None


async def _discard(request: Request, limit: int) -> None:
    seen = 0
    try:
        async for chunk in request.stream():
            seen += len(chunk)
            if seen > limit:
                break
    except Exception:
        pass


@app.middleware("http")
async def bounded_body(request: Request, call_next):
    if request.url.path == "/api/plan":
        declared = request.headers.get("content-length")
        rejection = _body_rejection(declared)
        if rejection is not None:
            if declared and declared.isdigit():
                await _discard(request, min(int(declared), MAX_DRAIN_BYTES))
            return rejection
    return await call_next(request)


def _taste() -> TasteProfile:
    path = HERE.parent / "state" / "taste.json"
    if path.exists():
        return TasteProfile.from_json(path.read_text(encoding="utf-8"))
    taste = TasteProfile()
    taste.observe(["science", "museum"], liked=True)
    return taste


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((HERE / "index.html").read_text(encoding="utf-8"))


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "offline": not bool(os.getenv("QLOO_API_KEY"))}


@app.post("/api/plan")
def plan(request: PlanRequest) -> JSONResponse:
    client = QlooClient(offline=not bool(os.getenv("QLOO_API_KEY")))
    route = CultureAgent(client, _taste()).plan(request.city, request.mood, request.minutes)
    payload = route.as_dict()
    payload["mode"] = "LIVE" if client.api_key and not client.offline else "OFFLINE FIXTURES"
    return JSONResponse(payload)
