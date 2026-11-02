# CCA-F Domain2: Tool use — TwiML is the "output tool" that controls the phone call
# INTERVIEW: Twilio executes TwiML verbs sequentially; <Gather> opens a speech collection window

from __future__ import annotations

import os


def _base_url() -> str:
    return os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def greeting_twiml(audio_filename: str) -> str:
    """TwiML: play the greeting audio then gather caller speech."""
    audio_url = f"{_base_url()}/audio/{audio_filename}"
    gather_url = f"{_base_url()}/gather"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{audio_url}</Play>
  <Gather input="speech" language="ml-IN" speechTimeout="auto"
          action="{gather_url}" method="POST" timeout="8">
  </Gather>
  <Redirect method="POST">{_base_url()}/voice</Redirect>
</Response>"""


def gather_twiml(audio_filename: str) -> str:
    """TwiML: play agent reply then gather next caller turn."""
    audio_url = f"{_base_url()}/audio/{audio_filename}"
    gather_url = f"{_base_url()}/gather"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{audio_url}</Play>
  <Gather input="speech" language="ml-IN" speechTimeout="auto"
          action="{gather_url}" method="POST" timeout="8">
  </Gather>
  <Redirect method="POST">{_base_url()}/voice</Redirect>
</Response>"""


def goodbye_twiml(audio_filename: str) -> str:
    """TwiML: play farewell and hang up."""
    audio_url = f"{_base_url()}/audio/{audio_filename}"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{audio_url}</Play>
  <Hangup/>
</Response>"""
