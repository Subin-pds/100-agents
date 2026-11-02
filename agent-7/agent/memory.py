"""In-context message history for the ReAct loop."""

from typing import Any


class MessageHistory:
    def __init__(self) -> None:
        self._messages: list[dict[str, Any]] = []

    def add_user(self, content: str | list) -> None:
        self._messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str | list) -> None:
        self._messages.append({"role": "assistant", "content": content})

    def all(self) -> list[dict[str, Any]]:
        return list(self._messages)

    def __len__(self) -> int:
        return len(self._messages)
