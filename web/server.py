"""Small web surface for CultureRoute: one page, one JSON endpoint, no build step."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from cultureroute.agent import CultureAgent
from cultureroute.qloo import QlooClient
from cultureroute.taste import TasteProfile

HERE = Path(__file__).resolve().parent
app = FastAPI(title="CultureRoute", version="0.2.0")


class PlanRequest(BaseModel):
    city: str = "Berlin"
    mood: str = "curious"
    minutes: int = 180


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
