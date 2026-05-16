"""In-context message history for the ReAct agent.

CCA-F Domain 5 — Context Management:
    This class IS the agent's memory. LLMs are stateless — every API call is
    independent. 'Memory' is achieved by keeping a list of past messages and
    re-sending it in full with every new call. This is called in-context memory
    (also: conversation buffer memory in LangChain terminology).

    Trade-off: As the conversation grows, so does the token count and cost.
    Agent 2 will add sliding-window and summarization strategies to address this.
"""

# INTERVIEW: What are the limits of in-context memory? The context window.
# For claude-sonnet-4-5 that's ~200K tokens — enough for long conversations,
# but not infinite. Production agents need a memory management strategy.

from typing import Any


class MessageHistory:
    """Maintains the full conversation history sent to the LLM each turn.

    CCA-F Domain 5 — Statelessness:
        The Anthropic API expects messages in alternating user/assistant roles.
        This class enforces that structure and provides a clean interface for
        the agent loop to append turns without managing raw dicts directly.
    """

    def __init__(self) -> None:
        # INTERVIEW: Why a list of dicts? Because that is exactly the format
        # the Anthropic messages API expects. No translation layer needed.
        self._messages: list[dict[str, Any]] = []

    def add_user(self, content: str | list) -> None:
        """Append a user turn. Content can be a string or a list of content blocks."""
        # CCA-F Domain 5: Tool results are injected as user-role messages
        # containing tool_result content blocks — not as a new user message.
        # This is the Anthropic API's required format for feeding tool output
        # back into the conversation.
        self._messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str | list) -> None:
        """Append an assistant turn. Content is typically a list of content blocks."""
        # CCA-F Domain 1: The assistant turn during tool use contains both
        # text blocks (Thought) and tool_use blocks (Action). Both are stored
        # verbatim so the next call to the LLM has full context.
        self._messages.append({"role": "assistant", "content": content})

    def all(self) -> list[dict[str, Any]]:
        """Return a copy of the full message list to pass to the API."""
        # INTERVIEW: Why return a copy? Defensive programming — the caller
        # should not be able to mutate the internal history by accident.
        return list(self._messages)

    def __len__(self) -> int:
        return len(self._messages)
