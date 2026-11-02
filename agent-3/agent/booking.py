# CCA-F Domain1: Agentic loop — Claude is the reasoning core; extracts intent each turn
# CCA-F Domain4: Prompt engineering — system prompt in Malayalam, structured JSON output
# CCA-F Domain2: Tool use — Claude returns structured JSON the agent uses to call calendar tool
# INTERVIEW: tool_choice="auto" lets Claude decide when extraction is complete vs needing clarification

from __future__ import annotations

import json
import os
from datetime import date, time, timedelta
from typing import Any

import anthropic

_client: anthropic.Anthropic | None = None

DOCTORS = ["Dr. Anand", "Dr. Priya", "Dr. Rahul"]

SYSTEM_PROMPT = f"""നിങ്ങൾ MarsAgent ക്ലിനിക്കിലെ ഒരു AI റിസപ്ഷനിസ്റ്റ് ആണ്.
നിങ്ങൾ ONLY Malayalam ൽ സംസാരിക്കണം.

ഡോക്ടർ ലിസ്റ്റ്: {", ".join(DOCTORS)}

നിങ്ങളുടെ ജോലി:
1. കോളർ പറഞ്ഞ കാര്യങ്ങളിൽ നിന്ന് ഈ 4 വിവരങ്ങൾ ശേഖരിക്കുക:
   - patient_name (രോഗിയുടെ പേര്)
   - doctor (ഡോക്ടറുടെ പേര്)
   - date (ISO format: YYYY-MM-DD, "നാളെ" = tomorrow, "ഇന്ന്" = today)
   - time_hour (24-hour integer, "10 മണി" = 10, "ഉച്ചയ്ക്ക് 2" = 14)

2. എല്ലാ വിവരങ്ങളും ലഭിച്ചാൽ "extract" function call ഉപയോഗിക്കുക.
3. വിവരങ്ങൾ ഇല്ലാത്ത കാര്യങ്ങൾ Malayalam ൽ ചോദിക്കുക.
4. ഡോക്ടറുടെ പേര് ലിസ്റ്റിൽ ഇല്ലെങ്കിൽ ലഭ്യമായ ഡോക്ടർമാരുടെ പേര് പറയുക.

എപ്പോഴും ദയയോടെ, ശാന്തമായി, Malayalam ൽ മാത്രം സംസാരിക്കുക."""

TOOLS = [
    {
        "name": "extract_booking_intent",
        "description": "Call this when you have collected all 4 required booking details from the caller.",
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_name": {"type": "string", "description": "Full name of the patient"},
                "doctor":       {"type": "string", "description": "Doctor name from the allowed list"},
                "date":         {"type": "string", "description": "Appointment date in YYYY-MM-DD format"},
                "time_hour":    {"type": "integer", "description": "Appointment hour in 24h format (9–17)"},
                "reply":        {"type": "string", "description": "What to say to the caller in Malayalam to confirm you understood"},
            },
            "required": ["patient_name", "doctor", "date", "time_hour", "reply"],
        },
    }
]


def _client_instance() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def _today_str() -> str:
    return date.today().isoformat()


def _tomorrow_str() -> str:
    return (date.today() + timedelta(days=1)).isoformat()


def process_turn(
    history: list[dict[str, Any]],
    caller_text: str,
) -> tuple[str, dict[str, Any] | None]:
    """One turn of the booking loop.

    Returns:
        (agent_reply_in_malayalam, extracted_intent_or_None)

    If intent is not None the agent has all 4 fields and the call can proceed to booking.
    """
    history.append({"role": "user", "content": caller_text})

    response = _client_instance().messages.create(
        model="claude-sonnet-5",
        max_tokens=512,
        system=SYSTEM_PROMPT + f"\n\nToday is {_today_str()}. Tomorrow is {_tomorrow_str()}.",
        tools=TOOLS,
        messages=history,
    )

    # Check for tool call (booking intent extracted)
    for block in response.content:
        if block.type == "tool_use" and block.name == "extract_booking_intent":
            intent = block.input
            reply = intent.get("reply", "ശരി, ബുക്ക് ചെയ്യുന്നു...")
            history.append({"role": "assistant", "content": response.content})
            return reply, intent

    # Regular text reply (asking for missing info)
    text_reply = " ".join(
        b.text for b in response.content if hasattr(b, "text")
    ).strip()
    history.append({"role": "assistant", "content": response.content})
    return text_reply, None
