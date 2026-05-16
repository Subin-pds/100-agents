"""Raw Anthropic API wrapper — single call, full history each time."""

# CCA-F Domain 5: Context Management — the LLM is stateless. Every call must
# include the complete message history; there is no server-side memory.

import os
from typing import Any

import anthropic

# INTERVIEW: Why claude-sonnet-4-5 for dev? Speed and cost. Swap to opus for
# final demo. Model choice is a latency/cost/quality tradeoff — interviewers
# ask this. claude-opus-4-5 for production demo quality.
MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 4096


def get_client() -> anthropic.Anthropic:
    """Create and return an Anthropic client using the API key from the environment."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=api_key)


def call_llm(
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, Any]] | None = None,
) -> anthropic.types.Message:
    """Send the full message history to Claude and return the raw Message object.

    CCA-F Domain 5 — Statelessness:
        Every invocation sends the *entire* conversation from the beginning.
        The model has no session state between calls; 'memory' is the list we
        pass in. This is fundamental to how all LLM APIs work.

    CCA-F Domain 1 — Agentic Orchestration:
        The caller (ReactAgent) decides *when* to call this function and what
        history to send. The LLM decides *what to do next* (tool call or answer).
        That division of responsibility is the agent loop.
    """
    # INTERVIEW: Why rebuild the full message list on every call? Because the
    # Anthropic API (like all LLM APIs) is stateless — each HTTP request is
    # independent. The 'memory' is just a Python list we maintain and re-send.
    client = get_client()
    kwargs: dict[str, Any] = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": messages,
    }
    if tools:
        # CCA-F Domain 2: Tool Design — tools are declared as JSON Schema
        # objects. The LLM reads the name + description to decide which tool
        # to call. Wording of descriptions matters enormously.
        kwargs["tools"] = tools
    return client.messages.create(**kwargs)
