# CCA-F Domain2: Tool use — TTS is a tool the agent calls to produce audio output
# CCA-F Domain1: Agentic loop — TTS is the output layer; agent thinks → speaks
# INTERVIEW: gTTS uses Google Translate's TTS endpoint; lang="ml" = Malayalam

import hashlib
import os
from pathlib import Path

from gtts import gTTS

AUDIO_DIR = Path(__file__).parent.parent / "audio"
AUDIO_DIR.mkdir(exist_ok=True)


def text_to_speech(text: str) -> str:
    """Convert Malayalam text to .mp3. Returns the file path.

    Files are content-addressed so repeated phrases reuse cached audio.
    """
    slug = hashlib.md5(text.encode()).hexdigest()[:12]
    path = AUDIO_DIR / f"{slug}.mp3"

    if not path.exists():
        tts = gTTS(text=text, lang="ml", slow=False)
        tts.save(str(path))

    return str(path)


# ── Pre-baked clinic phrases ─────────────────────────────────────────────────
# Generate these once at startup so there's no delay on the first call.

GREETING = "നമസ്കാരം! ഇത് MarsAgent ക്ലിനിക്ക് ആണ്. ഡോക്ടറുടെ അപ്പോയ്ൻ്റ്മെൻ്റ് ബുക്ക് ചെയ്യാൻ നിങ്ങളുടെ പേര്, ഡോക്ടറുടെ പേര്, തീയതി, സമയം എന്നിവ പറയൂ."
SORRY    = "ക്ഷമിക്കണം, എനിക്ക് മനസ്സിലായില്ല. ദയവായി വീണ്ടും പറയൂ."
GOODBYE  = "നന്ദി! നിങ്ങളുടെ അപ്പോയ്ൻ്റ്മെൻ്റ് ബുക്ക് ചെയ്തിട്ടുണ്ട്. ആരോഗ്യം ആശംസിക്കുന്നു!"
FULL     = "ക്ഷമിക്കണം, ആ സമയം നിറഞ്ഞിരിക്കുന്നു. മറ്റൊരു സമയം ഉണ്ടോ?"


def prewarm() -> None:
    """Generate audio for all static phrases at startup."""
    for phrase in (GREETING, SORRY, GOODBYE, FULL):
        text_to_speech(phrase)
