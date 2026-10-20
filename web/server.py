"""Small web surface for CultureRoute: one page, one JSON endpoint, no build step."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
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
MAX_FEEDBACK_TAGS = 8
MAX_TAG_CHARS = 32


class PlanRequest(BaseModel):
    city: str = Field(default="Berlin", max_length=MAX_CITY_CHARS)
    mood: str = Field(default="curious", max_length=32)
    minutes: int = Field(default=180, ge=5, le=1440)


class FeedbackRequest(BaseModel):
    tags: list[str] = Field(default_factory=list, max_length=MAX_FEEDBACK_TAGS)
    liked: bool = True


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


_PROFILE: TasteProfile | None = None
_PROFILE_PATH: Path | None = None


def _taste_path() -> Path:
    """Read-only deployments keep serving routes; tests point the state at a tmp file."""
    override = os.getenv("CULTUREROUTE_TASTE_PATH")
    return Path(override) if override else HERE.parent / "state" / "taste.json"


def _taste() -> TasteProfile:
    """One profile per state path, so a feedback call is visible to the next plan."""
    global _PROFILE, _PROFILE_PATH
    path = _taste_path()
    if _PROFILE is None or _PROFILE_PATH != path:
        if path.exists():
            _PROFILE = TasteProfile.from_json(path.read_text(encoding="utf-8"))
        else:
            _PROFILE = TasteProfile()
            _PROFILE.observe(["science", "museum"], liked=True)
        _PROFILE_PATH = path
    return _PROFILE


def _persist(taste: TasteProfile) -> bool:
    try:
        _taste_path().write_text(taste.to_json(), encoding="utf-8")
        return True
    except OSError:
        return False


def _taste_summary(taste: TasteProfile) -> list[dict]:
    return [{"tag": tag, "weight": round(weight, 2)} for tag, weight in taste.top(5)]


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((HERE / "index.html").read_text(encoding="utf-8"))


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "offline": not bool(os.getenv("QLOO_API_KEY"))}


@app.get("/api/taste")
def taste() -> dict:
    profile = _taste()
    return {"top": _taste_summary(profile), "tags": len(profile.weights)}


@app.post("/api/feedback")
def feedback(request: FeedbackRequest) -> dict:
    """The observe half of the loop: a rating changes the weights the next plan reads."""
    tags = []
    for raw in request.tags:
        tag = raw.strip().lower()[:MAX_TAG_CHARS]
        if tag and tag not in tags:
            tags.append(tag)
    if not tags:
        raise HTTPException(status_code=422, detail="At least one tag is required.")
    profile = _taste()
    before = {tag: round(profile.weights.get(tag, 0.0), 2) for tag in tags}
    profile.observe(tags, request.liked)
    return {"updated": [{"tag": tag, "before": before[tag],
                         "after": round(profile.weights[tag], 2)} for tag in tags],
            "persisted": _persist(profile), "top": _taste_summary(profile)}


@app.post("/api/plan")
def plan(request: PlanRequest) -> JSONResponse:
    client = QlooClient(offline=not bool(os.getenv("QLOO_API_KEY")))
    profile = _taste()
    route = CultureAgent(client, profile).plan(request.city, request.mood, request.minutes)
    payload = route.as_dict()
    payload["mode"] = "LIVE" if client.api_key and not client.offline else "OFFLINE FIXTURES"
    payload["taste"] = _taste_summary(profile)
    return JSONResponse(payload)
