"""Speech I/O for Jarvis.

TTS: pyttsx3 — offline, free, no API key (SAPI5 on Windows,
NSSpeechSynthesizer on macOS, espeak on Linux).

STT: SpeechRecognition's keyless `recognize_google` — free, no account, no
API key, but it's the unofficial free endpoint (rate-limited, requires
internet). Swap for local Whisper if that becomes a problem, or for Google
Cloud Speech-to-Text if this needs to scale past one user.

Neither is chosen for voice quality/accuracy — both are chosen because they
work with zero setup and zero cost, which matters more for a prototype.
"""

import speech_recognition as sr
import pyttsx3

_engine = None
_recognizer = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = pyttsx3.init()
        _engine.setProperty("rate", 185)  # a bit faster than default; still driving-safe
    return _engine


def speak(text: str) -> None:
    """Speak text aloud. Blocks until playback finishes."""
    if not text:
        return
    engine = _get_engine()
    engine.say(text)
    engine.runAndWait()


def _get_recognizer() -> sr.Recognizer:
    global _recognizer
    if _recognizer is None:
        _recognizer = sr.Recognizer()
    return _recognizer


def listen(phrase_time_limit: float = 12) -> str | None:
    """Capture one spoken utterance from the default microphone and
    transcribe it. Returns None on silence/timeout or if the speech
    couldn't be understood — the caller should just listen again.
    """
    recognizer = _get_recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=phrase_time_limit)
        except sr.WaitTimeoutError:
            return None
    try:
        return recognizer.recognize_google(audio)
    except (sr.UnknownValueError, sr.RequestError):
        return None
