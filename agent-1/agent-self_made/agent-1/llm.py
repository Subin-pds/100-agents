
import os

import anthropic



def get_client(api_key: str | None) -> anthropic.Anthropic:
    """Create and return an Anthropic client using the API key from the environment."""

    if api_key is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
    return anthropic.Anthropic(api_key=api_key)



def call_llm(
        messages: list[dict[str, any]],
        system: str,
        tools: list[dict[str, any]] | None = None,
) -> anthropic.types.Message:
    
    client = get_client()

    kwargs: dict[str, any] = {
        "model" : "claude-sonnet-4-5",
        "max_tokens" : 4096,
        "system" : system,
        "messages" : messages
    }
    if tools is not None:
        kwargs["tools"] = tools

    return client.messages.create(**kwargs)



