# CCA-F Domain2: Tool use — wraps Whisper as an STT tool callable by the agent
# CCA-F Domain1: Agentic loop — STT is the sensory input layer of the call loop
# INTERVIEW: Whisper accepts a URL or file; language="ml" forces Malayalam decoding

import os
import httpx
from openai import OpenAI

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


async def transcribe_url(audio_url: str, twilio_sid: str, twilio_token: str) -> str:
    """Download Twilio recording and transcribe it via Whisper in Malayalam."""
    async with httpx.AsyncClient() as http:
        # Twilio recordings require Basic auth
        resp = await http.get(audio_url, auth=(twilio_sid, twilio_token), follow_redirects=True)
        resp.raise_for_status()
        audio_bytes = resp.content

    result = _get_client().audio.transcriptions.create(
        model="whisper-1",
        file=("recording.wav", audio_bytes, "audio/wav"),
        language="ml",  # ISO 639-1 for Malayalam
    )
    return result.text.strip()


def transcribe_file(path: str) -> str:
    """Transcribe a local audio file in Malayalam. Used by demo.py."""
    with open(path, "rb") as f:
        result = _get_client().audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language="ml",
        )
    return result.text.strip()
