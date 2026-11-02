"""FastAPI wrapper around the Jarvis LangGraph agent.

Run locally:
    uvicorn api:app --reload --port 8080

Stateless by design: the caller sends the full conversation history with
every request, and the reply is derived purely from that history + the new
message. No server-side memory of past turns is kept. This matters once
this runs on Azure Functions (Consumption plan) — a serverless instance can
be replaced between calls, so anything relying on in-process state (like
LangGraph's MemorySaver checkpointer) would silently lose context. Pushing
history into the request instead avoids needing a persistent store
(Redis/Cosmos DB) altogether — the client already has the history, since
it's the one that spoke it and heard the replies.
"""

import logging
import os
import re
import secrets
import uuid

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import ToolMessage
from pydantic import BaseModel

load_dotenv()

from agent import trip_log  # noqa: E402  (import after load_dotenv)
from agent.graph import build_graph  # noqa: E402  (import after load_dotenv)
from agent.tools import USER_AGENT  # noqa: E402  (import after load_dotenv)

logger = logging.getLogger("jarvis.api")

app = FastAPI(title="Agent 6 — Jarvis")
graph = build_graph()

NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"

# Jarvis is deployed public (--allow-unauthenticated on Cloud Run), and
# get_document hands back links to personal ID documents — so every /query
# call must carry the PIN set here. Fails closed: an unset JARVIS_PIN
# rejects everything rather than silently leaving the gate open.
JARVIS_PIN = os.environ.get("JARVIS_PIN")


class Turn(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class GeoPoint(BaseModel):
    lat: float
    lon: float
    speed: float | None = None  # GPS ground speed in m/s, from navigator.geolocation


class QueryRequest(BaseModel):
    message: str
    history: list[Turn] = []
    location: GeoPoint | None = None  # real GPS from the client, if granted
    pin: str = ""


class QueryResponse(BaseModel):
    reply: str
    action_url: str | None = None  # link to open, from play_music/navigate_to/get_document


ACTION_TOOLS = {"play_music", "navigate_to", "get_document"}
URL_PATTERN = re.compile(r"https?://\S+")


def _extract_action_url(messages: list) -> str | None:
    """Find the URL from the most recent play_music/navigate_to tool call
    in this turn — pulled from the tool's actual output, not the LLM's
    paraphrased reply, so it can't be dropped or mangled in retelling.
    """
    for message in reversed(messages):
        if isinstance(message, ToolMessage) and message.name in ACTION_TOOLS:
            match = URL_PATTERN.search(str(message.content))
            if match:
                return match.group(0)
    return None


def _reverse_geocode(point: GeoPoint) -> str | None:
    """Resolve GPS coordinates to a human-readable place name via Nominatim.

    Returns None on any failure — GPS is a nice-to-have, not worth failing
    the whole request over (the agent falls back to get_current_location's
    IP-based guess when no location note is injected).
    """
    try:
        resp = requests.get(
            NOMINATIM_REVERSE_URL,
            params={"lat": point.lat, "lon": point.lon, "format": "json"},
            headers={"User-Agent": USER_AGENT},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json().get("display_name")
    except Exception as exc:
        logger.warning("reverse geocode failed: %s", exc)
        return None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    if not JARVIS_PIN or not secrets.compare_digest(request.pin, JARVIS_PIN):
        raise HTTPException(status_code=401, detail="invalid or missing pin")

    messages = [(turn.role, turn.content) for turn in request.history]
    messages.append(("user", request.message))

    current_location = _reverse_geocode(request.location) if request.location else None
    current_speed_kmh = (
        round(request.location.speed * 3.6, 1)
        if request.location and request.location.speed is not None
        else None
    )

    # build_graph() always attaches a checkpointer, which requires a
    # thread_id per invoke — a fresh, never-reused one here. It's not used
    # for cross-call memory (the client supplies full history above), only
    # to satisfy the graph's internal requirement for one.
    config = {
        "configurable": {
            "thread_id": str(uuid.uuid4()),
            "current_location": current_location,
            "current_speed_kmh": current_speed_kmh,
        }
    }
    result = graph.invoke({"messages": messages}, config=config)
    return QueryResponse(
        reply=result["messages"][-1].content,
        action_url=_extract_action_url(result["messages"]),
    )


class TripDistanceRequest(BaseModel):
    date: str  # YYYY-MM-DD, the client's local date (not the server's — avoids
    # midnight-boundary mismatches between wherever Cloud Run happens to run
    # and wherever the car actually is)
    km_travelled: float  # cumulative total for that date, not a delta — the
    # client owns the running sum and overwrites the file's value each call
    pin: str = ""


@app.post("/trip/distance")
def trip_distance(request: TripDistanceRequest) -> dict:
    if not JARVIS_PIN or not secrets.compare_digest(request.pin, JARVIS_PIN):
        raise HTTPException(status_code=401, detail="invalid or missing pin")
    try:
        trip_log.update_km_travelled(request.km_travelled, day=request.date)
    except Exception as exc:
        logger.warning("trip distance update failed: %s", exc)
        raise HTTPException(status_code=502, detail="trip log unavailable")
    return {"status": "ok"}


@app.get("/sw.js")
def service_worker() -> FileResponse:
    # no-cache (not no-store) so the browser always revalidates via
    # ETag/Last-Modified instead of possibly serving a stale copy from its
    # own HTTP cache — the service worker file is what propagates every
    # other update, so it can't itself go stale.
    return FileResponse(
        "static/sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


# Mounted last so it never shadows the routes above — StaticFiles(html=True)
# falls back to index.html for "/", serving the voice-client PWA there.
app.mount("/", StaticFiles(directory="static", html=True), name="static")
