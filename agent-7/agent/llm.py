"""Anthropic API wrapper — single call, full history each time."""

import os
from typing import Any

import anthropic

MODEL = "claude-sonnet-5"
MAX_TOKENS = 4096


def get_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=api_key)


def call_llm(
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, Any]] | None = None,
) -> anthropic.types.Message:
    client = get_client()
    kwargs: dict[str, Any] = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools
    return client.messages.create(**kwargs)
