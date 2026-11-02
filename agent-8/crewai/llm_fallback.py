"""Gemini LLM that falls back to the next model when the free tier is overloaded.

Free-tier Gemini regularly answers 503 (high demand), 429 (quota exhausted) or
504 (timeout). A crew run makes dozens of calls, so one busy model would kill
the whole run; instead each call walks down a chain of models and stays on the
first one that answers.
"""

import os

from crewai.llms.providers.gemini.completion import GeminiCompletion
from google.genai import errors

RETRYABLE_CODES = {429, 500, 503, 504}

# Ordered by quality; the lite models are less capable but rarely overloaded.
# Override with FALLBACK_MODELS in .env (comma-separated).
DEFAULT_CHAIN = [
    "gemini-2.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
]


def _fallback_chain() -> list[str]:
    configured = os.getenv("FALLBACK_MODELS", "")
    models = [m.strip().removeprefix("gemini/") for m in configured.split(",") if m.strip()]
    return models or DEFAULT_CHAIN


class FallbackGemini(GeminiCompletion):
    fallback_models: list[str] = []

    def call(self, *args, **kwargs):
        chain = [self.model] + [m for m in self.fallback_models if m != self.model]
        last_error: Exception | None = None
        for model in chain:
            # Switching self.model is enough: GeminiCompletion reads it on every
            # request, and staying switched keeps later calls off the busy model.
            self.model = model
            try:
                return super().call(*args, **kwargs)
            except errors.APIError as exc:
                if exc.code not in RETRYABLE_CODES:
                    raise
                print(f"[fallback] {model} returned {exc.code}, trying next model")
                last_error = exc
        raise last_error


def gemini_with_fallback(env_var: str) -> FallbackGemini:
    """Build a FallbackGemini whose first choice comes from env_var (or LLM_MODEL)."""
    chain = _fallback_chain()
    first = os.getenv(env_var) or os.getenv("LLM_MODEL") or chain[0]
    first = first.removeprefix("gemini/")
    return FallbackGemini(model=first, fallback_models=chain)


def make_llm(env_var: str):
    """Gemini (with fallback) by default; any other provider set in .env is used as-is."""
    chosen = os.getenv(env_var) or os.getenv("LLM_MODEL") or ""
    if chosen and not chosen.startswith("gemini/"):
        from crewai import LLM

        return LLM(model=chosen)
    return gemini_with_fallback(env_var)
