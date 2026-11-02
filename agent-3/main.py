# CCA-F Domain1: Agentic loop — FastAPI orchestrates the full call loop across HTTP turns
# CCA-F Domain2: Tool use — each webhook is a tool invocation in the agentic pipeline
# CCA-F Domain5: Context management — call sessions stored in memory; history trimmed per call
# INTERVIEW: Twilio is stateless; we maintain session by keying on CallSid

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import date, time
from pathlib import Path
from typing import Any

import structlog
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

load_dotenv()

from agent.booking import process_turn
from agent.calendar import get_calendar
from twiml.responses import gather_twiml, goodbye_twiml, greeting_twiml
from voice.stt import transcribe_url
from voice.tts import GOODBYE, GREETING, SORRY, prewarm, text_to_speech

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

# ── Session store ────────────────────────────────────────────────────────────
# Keyed by Twilio CallSid; holds conversation history for that call
_sessions: dict[str, list[dict[str, Any]]] = {}

AUDIO_DIR = Path(__file__).parent / "audio"
AUDIO_DIR.mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    prewarm()
    get_calendar()
    log.info("startup_complete", clinic=os.getenv("CLINIC_NAME", "MarsAgent Clinic"))
    yield
    _sessions.clear()


app = FastAPI(title="MarsAgent Malayalam Clinic Bot", lifespan=lifespan)
app.mount("/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")


# ── /voice — entry point when a call arrives ────────────────────────────────
@app.post("/voice")
async def voice_entry():
    """Twilio calls this when someone dials the clinic number."""
    greeting_path = text_to_speech(GREETING)
    filename = Path(greeting_path).name
    log.info("call_received")
    return Response(content=greeting_twiml(filename), media_type="application/xml")


# ── /gather — handles each spoken turn from the caller ──────────────────────
@app.post("/gather")
async def gather(
    CallSid: str = Form(...),
    SpeechResult: str = Form(default=""),
    RecordingUrl: str = Form(default=""),
    Confidence: float = Form(default=0.0),
):
    """Twilio posts here after each speech gather."""
    # Prefer Twilio's built-in transcription if available; else fall back to Whisper
    caller_text = SpeechResult.strip()

    if not caller_text and RecordingUrl:
        # Transcribe via Whisper when built-in speech recognition returns empty
        caller_text = await transcribe_url(
            RecordingUrl,
            os.environ["TWILIO_ACCOUNT_SID"],
            os.environ["TWILIO_AUTH_TOKEN"],
        )

    log.info("caller_spoke", call=CallSid, text=caller_text, confidence=Confidence)

    if not caller_text:
        sorry_path = text_to_speech(SORRY)
        return Response(content=gather_twiml(Path(sorry_path).name), media_type="application/xml")

    # Retrieve or create session history for this call
    history = _sessions.setdefault(CallSid, [])

    # Claude processes the turn
    reply_text, intent = process_turn(history, caller_text)
    log.info("agent_reply", call=CallSid, reply=reply_text, intent=intent)

    if intent:
        # All booking details extracted — try to book
        cal = get_calendar()
        slot = cal.book(
            doctor=intent["doctor"],
            on_date=date.fromisoformat(intent["date"]),
            at_time=time(int(intent["time_hour"]), 0),
            patient=intent["patient_name"],
        )

        if slot:
            confirm_text = cal.confirmation_message(slot)
            confirm_path = text_to_speech(confirm_text + " " + GOODBYE)
            _sessions.pop(CallSid, None)
            return Response(
                content=goodbye_twiml(Path(confirm_path).name),
                media_type="application/xml",
            )
        else:
            # Slot not available — tell caller in Malayalam
            full_text = "ക്ഷമിക്കണം, ആ സമയം ലഭ്യമല്ല. മറ്റൊരു സമയം ഉണ്ടോ?"
            reply_path = text_to_speech(full_text)
            # Clear intent from history so Claude asks again
            return Response(
                content=gather_twiml(Path(reply_path).name),
                media_type="application/xml",
            )

    # Still collecting info — play reply and gather next turn
    reply_path = text_to_speech(reply_text)
    return Response(content=gather_twiml(Path(reply_path).name), media_type="application/xml")


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "clinic": os.getenv("CLINIC_NAME", "MarsAgent Clinic")}
