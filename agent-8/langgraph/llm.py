"""Model selection for the LangGraph implementation.

Reads the same .env settings as the CrewAI version (LLM_MODEL, RESEARCH_MODEL,
ADVISOR_MODEL, FALLBACK_MODELS), so both frameworks are compared on the same models.

Contrast with crewai/llm_fallback.py: CrewAI needed a custom LLM subclass to
fall back between models; LangChain has it built in as Runnable.with_fallbacks().
"""

import os

from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

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


def _gemini(model: str) -> ChatGoogleGenerativeAI:
    # max_retries=0: fail fast on 429/503 so the fallback kicks in immediately
    # instead of the SDK sleeping through several backoff retries first.
    return ChatGoogleGenerativeAI(model=model, max_retries=0, timeout=90)


def make_llm(env_var: str = "LLM_MODEL", tools: list | None = None):
    """Return a chat model for env_var, falling back to LLM_MODEL, then Gemini 2.5 Flash.

    Settings use CrewAI's "provider/model" format so one .env serves both
    implementations: "gemini/..." gets the fallback chain, "anthropic/..." is used as-is.
    Pass tools to get a model that can call them.
    """
    chosen = os.getenv(env_var) or os.getenv("LLM_MODEL") or "gemini/gemini-2.5-flash"

    def prepare(model):
        return model.bind_tools(tools) if tools else model

    if chosen.startswith("anthropic/"):
        return prepare(ChatAnthropic(model=chosen.removeprefix("anthropic/")))

    first = chosen.removeprefix("gemini/")
    rest = [m for m in _fallback_chain() if m != first]
    # Tools are bound to each model *before* wrapping: the object returned by
    # with_fallbacks() has no bind_tools(), so binding afterwards would fail.
    return prepare(_gemini(first)).with_fallbacks([prepare(_gemini(m)) for m in rest])
