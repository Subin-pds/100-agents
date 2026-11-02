'''This is a copy file for llm.py used for learning purpose for coding llm
'''
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
    configured = os.getenv("FALLBACK_MODELS","")
    models = [m.strip().removeprefix("gemini/") for m in configured.split(",") if m.strip()]
    return models or DEFAULT_CHAIN

def _gemini(model:str) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(model=model, max_retries=0, timeout=90)


def make_llm(env_var : str ="LLM_MODEL"):
    choosen = os.getenv(env_var) or os.getenv("LLM_MODEL") or "gemini-2.5-flash"

    if choosen.startswith("anthropic/"):
        return ChatAnthropic(model=choosen.removeprefix('anthropic/'))

    first = choosen.removeprefix('gemini/')
    rest = [m for m in _fallback_chain() if m!=first]
    return _gemini(first).with_fallbacks([_gemini(m) for m in rest])